#!/usr/bin/env python3
"""CDP 测试 v18: 构造识别结果调用 recognize_callback"""
import json, subprocess, urllib.request, websocket, time, base64

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

# 先找 recognize_callback 完整名
js0 = "(function(){var ks=Object.keys(window).filter(function(k){return k.indexOf('recognize')>=0});return JSON.stringify(ks)})()"
names = json.loads(cdp_eval(ws, js0))
print("recognize 函数:", names, flush=True)
cb = names[-1]  # recognize_callback_xxx

# 构造 base64url 编码的 result
result = {"recognizeResult": "+", "pathPoints": [], "answer": 1, "showReductionFraction": 0}
raw = json.dumps(result).encode()
b64 = base64.b64encode(raw).decode().rstrip("=").replace("+", "-").replace("/", "_")
print("构造参数:", b64, flush=True)

# 调用
js1 = f"window['{cb}']('{b64}'); 'called'"
try:
    val = cdp_eval(ws, js1)
    print("调用结果:", val, flush=True)
    time.sleep(1.5)
    js2 = "(function(){var p=document.getElementById('primary-question-wrap');var s=document.getElementById('second-question-wrap');return JSON.stringify({primary:p?p.innerText:'none',second:s?s.innerText:'none'})})()"
    val2 = cdp_eval(ws, js2)
    print("题目状态:", val2, flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
