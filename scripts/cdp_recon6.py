#!/usr/bin/env python3
"""CDP 侦察 v6: 找 Vue 实例与答案提交逻辑"""
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

probes = [
    ("Vue 实例位置", "Array.from(document.querySelectorAll('*')).filter(function(e){return e.__vue__}).map(function(e){return e.tagName+'.'+String(e.className).substring(0,40)}).slice(0,8).join(' | ')"),
    ("Vue $data", """(function(){
      var el = Array.from(document.querySelectorAll('*')).filter(function(e){return e.__vue__})[0];
      if(!el) return 'no vue';
      var v = el.__vue__;
      var out = {name: v.$options.name || 'anon', data: Object.keys(v.$data||{}).slice(0,50)};
      return JSON.stringify(out);
    })()"""),
    ("window 上回调名的独特部分", """(function(){
      var ks = Object.keys(window).filter(function(k){return k.indexOf('_callback_')>=0});
      return ks.length + ' callbacks; sample: ' + ks.slice(0,5).join(',');
    })()"""),
    ("原生桥对象", """(function(){
      var out=[];
      for(var k in window){
        var v = window[k];
        if(v && typeof v==='object' && /(Leo|Fenbi|Native|Bridge|Android|JSBridge|client|App)/i.test(k) && Object.keys(v).length<30){
          out.push(k + ':' + Object.keys(v).slice(0,15).join(','));
        }
      }
      return out.slice(0,20).join('\n');
    })()"""),
]
for name, js in probes:
    try:
        val = cdp_eval(ws, js)
        print("=== " + name + " ===", flush=True)
        print(str(val)[:2000], flush=True)
    except Exception as e:
        print("=== " + name + " === ERR " + str(e), flush=True)
