#!/usr/bin/env python3
"""CDP 侦察 v21: 原生桥对象"""
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

# 枚举 window 上的非标准对象 (原生注入的桥)
js = """(function(){
  var out = [];
  for(var k in window){
    var v = window[k];
    if(v && typeof v === 'object' && k !== 'window' && k !== 'self' && k !== 'document' && k !== 'navigator' && k !== 'location' && k !== 'history' && k !== 'performance' && k !== 'localStorage' && k !== 'sessionStorage'){
      var isNative = /native code/.test(String(v));
      var keys = Object.keys(v).slice(0,10);
      if(keys.length > 0 || isNative){
        out.push(k + ' (native=' + isNative + '): ' + keys.join(','));
      }
    }
  }
  return out.slice(0,30).join('\n');
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== window 对象 ===", flush=True)
    print(str(val)[:3000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
