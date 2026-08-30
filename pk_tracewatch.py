#!/usr/bin/env python3
"""轨迹监控: 记录手动答题时的手写轨迹结构"""
import json
import subprocess
import time
import urllib.request

import websocket

ADB = "/opt/homebrew/bin/adb"
PKG = "com.fenbi.android.leo"
ORAL_MODULE = "https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js"
LOG_FILE = "/tmp/pk_tracewatch.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_pages():
    pid = subprocess.check_output([ADB, "shell", "pidof", PKG]).decode().strip()
    if not pid:
        return []
    subprocess.run([ADB, "forward", "tcp:9333",
                    f"localabstract:webview_devtools_remote_{pid}"], capture_output=True)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:9333/json", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []


def get_trace(cdp_ws):
    js = """(async function(){
      try {
        var m = await System.import('%s');
        var api = m.d();
        var wc = api.writeContent ? api.writeContent.value : null;
        var cfg = api.recognizeConfig ? api.recognizeConfig.value : null;
        var q = document.querySelector('.primary-question:not([style*="none"])');
        return JSON.stringify({
          strokes: wc ? wc.length : -1,
          firstStrokePts: (wc && wc.length && wc[0]) ? wc[0].length : 0,
          firstPts: (wc && wc.length && wc[0]) ? JSON.stringify(wc[0].slice(0,5)) : 'none',
          cfg: cfg ? {answers: cfg.answers, qi: cfg.questionIndex} : 'none',
          q: q ? q.innerText : ''
        });
      } catch(e) { return 'ERR:' + String(e).substring(0,100); }
    })()""" % ORAL_MODULE
    ws = websocket.create_connection(cdp_ws, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            r = msg.get("result", {}).get("result", {})
            ws.close()
            return r.get("value")


def main():
    log("=== 轨迹监控: 请手动答题 ===")
    last_strokes = -1
    last_q = ""
    last_submit = 0

    while True:
        pages = get_pages()
        if not pages:
            time.sleep(1)
            continue
        page = None
        for p in pages:
            u = p.get("url", "")
            if "leo-web-oral" in u and ("exercise" in u):
                page = p
                break
        if not page:
            time.sleep(0.5)
            continue

        try:
            val = get_trace(page["webSocketDebuggerUrl"])
            if not val or val.startswith("ERR"):
                time.sleep(0.3)
                continue
            d = json.loads(val)
            strokes = d.get("strokes", -1)
            q = d.get("q", "").strip()
            first_pts = d.get("firstPts", "none")

            # 题目变化
            if q != last_q and q:
                log(f"题目: [{q.replace(chr(10),'|')}] 答案池={d.get('cfg')}")
                last_q = q

            # 手写开始 (轨迹增加)
            if strokes > last_strokes and strokes > 0:
                log(f"  手写: {strokes}笔, 首笔{first_pts[:80]}")
                last_strokes = strokes

            # 手写清空 (提交后 resetCanvas)
            if strokes == 0 and last_strokes > 0:
                log(f"  [提交后清空] 上一笔数={last_strokes}")
                last_strokes = 0
                last_submit = time.time()

        except Exception as e:
            pass
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("已停止")
