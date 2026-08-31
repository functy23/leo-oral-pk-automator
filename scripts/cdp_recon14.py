#!/usr/bin/env python3
"""CDP 侦察 v14: 找 e 函数/识别逻辑"""
import json, subprocess, urllib.request, websocket

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

# 1. 检查是否有 recognizer 相关对象
js = """(function(){
  var out = {};
  for(var k in window){
    var v = window[k];
    if(typeof v === 'function' && /(recogn|hand|write|stroke|answer|submit|commit)/i.test(k)){
      out[k] = String(v).substring(0,200);
    }
  }
  return JSON.stringify(out);
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== 相关函数 ===", flush=True)
    print(str(val)[:3000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)

# 2. 检查页面引用的脚本 (找识别模块)
js2 = """(function(){
  var scripts = Array.from(document.querySelectorAll('script[src]')).map(function(s){return s.src});
  return JSON.stringify(scripts);
})()"""
try:
    val2 = cdp_eval(ws, js2)
    print("\n=== 脚本列表 ===", flush=True)
    print(str(val2)[:3000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
