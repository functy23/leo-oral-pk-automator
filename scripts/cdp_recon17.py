#!/usr/bin/env python3
"""CDP 侦察 v17: 通过 SystemJS 访问识别模块"""
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

# 通过 System.get 或 System.import 访问模块
js = """(async function(){
  var out = {hasSystem: typeof System !== 'undefined'};
  try {
    // SystemJS 的 get 方法
    out.getType = typeof System.get;
    out.importType = typeof System.import;
    // 尝试获取模块注册表
    var keys = [];
    if (System.getRegistry) {
      var reg = System.getRegistry();
      keys = Array.from(reg.keys()).filter(function(k){return /oral|index|DMg/.test(k)});
    }
    out.registryKeys = keys.slice(0,20);
  } catch(e) { out.err = String(e); }
  return JSON.stringify(out);
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== SystemJS 检查 ===", flush=True)
    print(str(val)[:2000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
