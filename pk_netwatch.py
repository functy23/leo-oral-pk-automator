#!/usr/bin/env python3
"""精准监控 v2: 抓取答题提交网络请求 + 手写轨迹"""
import json
import subprocess
import time
import urllib.request

import websocket

ADB = "/opt/homebrew/bin/adb"
PKG = "com.fenbi.android.leo"
ORAL_MODULE = "https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js"
LOG_FILE = "/tmp/pk_netwatch.log"


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


def main():
    log("=== 精准监控: 抓取答题请求 ===")
    seen_requests = {}

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

        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
        try:
            # 开启 Network
            ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
            # 订阅请求
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                                "params": {"expression": "(function(){return document.body.innerText.substring(0,80)})()",
                                           "returnByValue": True}}))
            # 持续监听
            ws.settimeout(30)
            try:
                while True:
                    msg = json.loads(ws.recv())
                    method = msg.get("method", "")
                    if method == "Network.requestWillBeSent":
                        req = msg["params"]["request"]
                        url = req.get("url", "")
                        # 只记录答题相关请求
                        if any(k in url for k in ["answer", "submit", "recognize", "commit", "calculate", "pk/"]):
                            post = req.get("postData", "")
                            ts = time.strftime('%H:%M:%S')
                            key = url + post[:100]
                            if key not in seen_requests:
                                seen_requests[key] = True
                                log(f"请求: {url[-60:]}")
                                if post:
                                    log(f"  POST: {post[:400]}")
                    elif method == "Network.responseReceived":
                        pass
            except websocket.WebSocketTimeoutException:
                pass
        except Exception as e:
            log(f"异常: {e}")
        finally:
            try:
                ws.close()
            except Exception:
                pass
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("已停止")
