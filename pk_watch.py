#!/usr/bin/env python3
"""实时监控: 记录手动答题全过程的状态变化"""
import json
import subprocess
import sys
import time
import urllib.request

import websocket

ADB = "/opt/homebrew/bin/adb"
PKG = "com.fenbi.android.leo"
ORAL_MODULE = "https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js"
LOG_FILE = "/tmp/pk_watch.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


class CDP:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self._ws = None

    def connect(self):
        self._ws = websocket.create_connection(self.ws_url, timeout=10)
        return self

    def eval(self, js, timeout=15):
        if not self._ws:
            self.connect()
        self._ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True, "awaitPromise": True}
        }))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == 1:
                r = msg.get("result", {}).get("result", {})
                if r.get("subtype") == "error":
                    return None
                return r.get("value")

    def close(self):
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass


def get_pages():
    pid = subprocess.check_output([ADB, "shell", "pidof", PKG]).decode().strip()
    if not pid:
        return []
    subprocess.run([ADB, "forward", f"tcp:9333",
                    f"localabstract:webview_devtools_remote_{pid}"], capture_output=True)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{FORWARD_PORT}/json", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []


def snapshot(cdp):
    """采集一次完整状态快照"""
    js = """(async function(){
      var out = {};
      try {
        var m = await System.import('%s');
        var api = m.d();
        var cfg = api.recognizeConfig.value;
        out.cfg = cfg;
        // 计时器 (costTime)
        out.now = Date.now();
        // 手写板状态
        var wc = api.writeContent ? api.writeContent.value : null;
        out.strokeCount = wc ? wc.length : -1;
        out.strokePoints = wc && wc.length ? wc[0].length : 0;
        // 题目
        var q = document.querySelector('.primary-question:not([style*="none"])');
        out.qText = q ? q.innerText : '';
        // 答案区
        var blocks = document.querySelectorAll('.answer-block');
        var filled = [];
        for(var i=0;i<blocks.length;i++){
          var t = blocks[i].innerText.trim();
          if(t && t !== '?') filled.push(t);
        }
        out.filled = filled.slice(0,3);
        // 进度
        out.body = document.body.innerText.substring(0, 100);
      } catch(e) { out.err = String(e).substring(0,150); }
      return JSON.stringify(out);
    })()""" % ORAL_MODULE
    val = cdp.eval(js)
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return {"raw": val}


def main():
    log("=== 实时监控: 请手动完成一局 PK ===")
    last_q = ""
    last_cfg_qi = None
    last_stroke = -1
    last_filled = ""

    while True:
        pages = get_pages()
        if not pages:
            time.sleep(1)
            continue
        page = None
        for p in pages:
            u = p.get("url", "")
            if "leo-web-oral" in u and ("exercise" in u or "pk" in u):
                page = p
                break
        if not page:
            time.sleep(1)
            continue

        cdp = CDP(page["webSocketDebuggerUrl"])
        try:
            snap = snapshot(cdp)
            if not snap:
                time.sleep(0.5)
                continue
            q = snap.get("qText", "").strip()
            qi = snap.get("cfg", {}).get("questionIndex")
            strokes = snap.get("strokeCount", -1)
            filled = json.dumps(snap.get("filled", []), ensure_ascii=False)
            now = snap.get("now", 0)
            ts = time.strftime('%H:%M:%S')

            # 检测题目变化
            if q != last_q and q:
                log(f"题目变化: [{q.replace(chr(10),'|')}] qi={qi} strokes={strokes}")
                last_q = q
                last_cfg_qi = qi

            # 检测手写开始
            if strokes > last_stroke and strokes > 0:
                log(f"  手写轨迹: {strokes} 笔 (stroke0={snap.get('strokePoints',0)}点)")
                last_stroke = strokes

            # 检测答案提交 (filled 变化)
            if filled != last_filled and filled != "[]":
                log(f"  答案区: {filled} @ {ts}")
                last_filled = filled

            # 每5秒记录计时器状态
            if int(time.time()) % 5 == 0:
                log(f"  [心跳] qi={qi} strokes={strokes} filled={filled}")
                time.sleep(1)

        except Exception as e:
            log(f"异常: {e}")
        finally:
            cdp.close()
        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("已停止")
