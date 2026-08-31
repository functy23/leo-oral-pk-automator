#!/usr/bin/env python3
"""CDP 侦察 v3: 修复转义, 看 DOM/Vue/题目"""
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
print("[+] ws:", ws)

# 用简单 JS (避免转义问题)
simple_js = [
    ("body children", "document.body.children.length + ' children; ids: ' + Array.from(document.body.querySelectorAll('[id]')).map(e=>e.id).slice(0,20).join(',')"),
    ("有 vue 的元素", "Array.from(document.querySelectorAll('*')).filter(e=>e.__vue__).slice(0,5).map(e=>e.tagName+'.'+String(e.className).substring(0,30)).join(' | ')"),
    ("题目文本", "document.body.innerText.replace(/\\n/g,' | ').substring(0,400)"),
    ("所有 input/button", "Array.from(document.querySelectorAll('input,button')).slice(0,20).map(e=>e.tagName+'.'+String(e.className).substring(0,30)+(e.value?'='+e.value:'')).join(' | ')"),
    ("webpack chunk 里的可疑模块", "(function(){ var k=Object.keys(window); return k.filter(function(x){return /(webpack|chunk|require)/i.test(x)}).slice(0,10).join(',') })()"),
]
for name, js in simple_js:
    try:
        val = cdp_eval(ws, js)
        print(f"\n=== {name} ===", flush=True)
        print(str(val)[:1500], flush=True)
    except Exception as e:
        print(f"\n=== {name} === ERR {e}", flush=True)
