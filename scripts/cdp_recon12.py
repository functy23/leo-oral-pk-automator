#!/usr/bin/env python3
"""CDP 侦察 v12: 分析 pt 函数与测试调用"""
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

# 分析: 用函数 toString 找 pt 和其他闭包变量
js = """(function(){
  var fn = window['recognize_callback_1787841452414_261'];
  var src = String(fn);
  // 提取闭包变量名 (从源码上下文推断)
  return JSON.stringify({
    src: src.substring(0, 500),
    name: fn.name
  });
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== recognize 源码 ===", flush=True)
    print(str(val)[:1500], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
