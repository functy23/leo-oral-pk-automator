#!/usr/bin/env python3
"""CDP 测试 v13: 调用 recognize 传测试数据"""
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

# 测试各种参数格式
tests = [
    ('"+"', "直接传 +"),
    ('"{\"result\":\"+\"}"', "JSON result"),
    ('"+\"-\"*\"/\""', "字符串数组?"),
]
for arg, desc in tests:
    js = f"window['recognize_callback_1787841452414_261']({arg}); 'called'"
    try:
        val = cdp_eval(ws, js)
        time.sleep(1)
        js2 = "(function(){var p=document.getElementById('primary-question-wrap');return p?p.innerText:'none'})()"
        val2 = cdp_eval(ws, js2)
        print(f"[{desc}] arg={arg} -> call={val} primary={val2}", flush=True)
    except Exception as e:
        print(f"[{desc}] ERR: {e}", flush=True)
