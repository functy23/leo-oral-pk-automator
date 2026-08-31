#!/usr/bin/env python3
"""CDP 测试 v20: SystemJS 访问识别模块"""
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

def cdp_eval(ws_url, js, timeout=20):
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close(); r = msg.get("result", {}).get("result", {})
            if r.get("subtype") == "error":
                return "ERR:" + str(r.get("description", ""))[:200]
            return r.get("value", "no-value")
    return None

ws = get_page_ws()

# 尝试多种方式访问模块
js_list = [
    ("System.import", "(async function(){ try { var m = await System.import('./index-legacy.DMgv2yXx.js'); return 'imported keys: ' + Object.keys(m); } catch(e) { return 'err: ' + e; } })()"),
    ("System.get(全路径)", "(function(){ try { var m = System.get('https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js'); return m ? 'keys: '+Object.keys(m) : 'null'; } catch(e) { return 'err: '+e; } })()"),
    ("System.get(短名)", "(function(){ try { var m = System.get('./index-legacy.DMgv2yXx.js'); return m ? 'keys: '+Object.keys(m) : 'null'; } catch(e) { return 'err: '+e; } })()"),
]
for name, js in js_list:
    try:
        val = cdp_eval(ws, js)
        print(f"=== {name} ===", flush=True)
        print(str(val)[:500], flush=True)
    except Exception as e:
        print(f"=== {name} === ERR {e}", flush=True)
