#!/usr/bin/env python3
"""CDP 侦察 v16: 找题目答案数据"""
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

# 从 window 找可能的模块引用
probes = [
    ("SystemJS 模块", "(function(){ var out=[]; for(var k in window){ if(k==='System'||k==='__webpack_require__'||k==='define') out.push(k); } return JSON.stringify(out) })()"),
    ("exercise 页面数据", """(function(){
      // 找所有元素含 data- 属性的题目数据
      var els = document.querySelectorAll('[data-answer], [data-question], [data-id]');
      return 'data-els: ' + els.length;
    })()"""),
    ("全局可访问的函数含 answer", """(function(){
      var out=[];
      for(var k in window){ if(typeof window[k]==='function' && /answer/i.test(k)) out.push(k); }
      return JSON.stringify(out.slice(0,20));
    })()"""),
]
for name, js in probes:
    try:
        val = cdp_eval(ws, js)
        print("=== " + name + " ===", flush=True)
        print(str(val)[:1000], flush=True)
    except Exception as e:
        print("=== " + name + " === ERR " + str(e), flush=True)
