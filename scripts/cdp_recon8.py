#!/usr/bin/env python3
"""CDP 侦察 v8: 回调前缀 (无正则)"""
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

# 不写正则, 直接在 JS 里用 split 处理
js = """(function(){
  var ks = Object.keys(window).filter(function(k){return k.indexOf('_callback_')>=0});
  var prefixes = {};
  ks.forEach(function(k){
    var parts = k.split('_callback_');
    var p = parts[0] + '_callback_';
    prefixes[p] = (prefixes[p]||0)+1;
  });
  var arr = Object.keys(prefixes).sort().map(function(p){return p + '(' + prefixes[p] + ')'});
  return arr.join(String.fromCharCode(10));
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== 回调前缀 ===", flush=True)
    print(str(val)[:4000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
