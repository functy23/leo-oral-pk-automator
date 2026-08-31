#!/usr/bin/env python3
"""CDP 验证 v26: 查看提交后的页面"""
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

def cdp_eval(ws_url, js, timeout=20):
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close(); r = msg.get("result", {}).get("result", {})
            return r.get("value", "no-value")
    return None

ws = get_page_ws()

# 查看页面状态 (无正则)
js = """(function(){
  var out = {};
  var blocks = document.querySelectorAll('.answer-block');
  var filled = [];
  for(var i=0;i<blocks.length;i++){
    var t = blocks[i].innerText.trim();
    if(t && t !== '?') filled.push(i + ':' + t);
  }
  out.filled = filled.slice(0,8);
  out.body = document.body.innerText.substring(0,300);
  return JSON.stringify(out);
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== 页面状态 ===", flush=True)
    print(str(val)[:1200], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
