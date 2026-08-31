#!/usr/bin/env python3
"""CDP 侦察 v11: 主动调用 recognize 测试"""
import json, subprocess, urllib.request, websocket, time

ADB = "/opt/homebrew/bin/adb"; PKG = "com.fenbi.android.leo"

def get_page_ws():
    pid = subprocess.check_output([ADB, "shell", "pidof", PKG]).decode().strip()
    subprocess.run([ADB, "forward", "tcp:9333", f"localabstract:webview_devtools_remote_{pid}"], capture_output=True)
    with urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=5) as resp:
        pages = json.loads(resp.read().decode())
    for p in pages:
        if "leo-web-oral" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"] if pages else None

def cdp_eval(ws_url, js, timeout=15):
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close(); r = msg.get("result", {}).get("result", {})
            return r.get("value", "no-value")
    return None

ws = get_page_ws()

# 1. 先看当前题目文本
js1 = "(function(){var p=document.getElementById('primary-question-wrap');var s=document.getElementById('second-question-wrap');return JSON.stringify({primary:p?p.innerText:'none',second:s?s.innerText:'none'})})()"
val = cdp_eval(ws, js1)
print("当前题目:", val, flush=True)

# 2. 找 recognize 回调完整名字
js2 = "(function(){var ks=Object.keys(window).filter(function(k){return k.indexOf('recognize')>=0});return JSON.stringify(ks)})()"
val2 = cdp_eval(ws, js2)
print("recognize 函数名:", val2, flush=True)
