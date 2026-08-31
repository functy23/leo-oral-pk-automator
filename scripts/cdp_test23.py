#!/usr/bin/env python3
"""CDP 测试 v23: System.import 完整 URL"""
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
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close(); r = msg.get("result", {}).get("result", {})
            if r.get("subtype") == "error":
                return "ERR:" + str(r.get("description", ""))[:300]
            return r.get("value", "no-value")
    return None

ws = get_page_ws()

js = """(async function(){
  var out = {};
  try {
    var m = await System.import('https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js');
    out.keys = Object.keys(m);
    out.dType = typeof m.d;
    if (m.d) {
      var api = m.d();
      out.apiKeys = Object.keys(api);
      out.api = api;
    }
  } catch(e) { out.err = String(e).substring(0,300); }
  return JSON.stringify(out);
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== System.import 结果 ===", flush=True)
    print(str(val)[:2000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
