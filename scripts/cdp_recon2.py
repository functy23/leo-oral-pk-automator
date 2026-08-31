#!/usr/bin/env python3
"""CDP 深度侦察: Vue 实例与题目结构"""
import json
import subprocess
import urllib.request
import websocket

ADB = "/opt/homebrew/bin/adb"
PKG = "com.fenbi.android.leo"

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
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            r = msg.get("result", {}).get("result", {})
            if r.get("subtype") == "error":
                return "ERR: " + str(r)
            return r.get("value")
    ws.close()
    return None

ws = get_page_ws()
print(f"[+] ws: {ws}")

probes = [
    ("Vue 根实例", """(function(){
      var app = document.querySelector('#app');
      var vue = app && app.__vue__;
      if(!vue) return 'no vue on #app';
      var out = {name: vue.$options.name || 'anon', dataKeys: Object.keys(vue.$data || {}).slice(0,40)};
      return JSON.stringify(out);
    })()"""),
    ("Vue 组件树", """(function(){
      var app = document.querySelector('#app');
      var vue = app && app.__vue__;
      if(!vue) return 'no vue';
      var names=[];
      function walk(v,d){ if(!v||d>5) return; names.push(' '.repeat(d)+ (v.$options.name||v.$options._componentTag||'anon')); for(var c of v.$children) walk(c,d+1); }
      walk(vue,0); return names.join('\n').substring(0,1500);
    })()"""),
    ("题目元素", """(function(){
      var els=[];
      document.querySelectorAll('*').forEach(function(e){
        var t=(e.className&&typeof e.className==='string')?e.className:'';
        if(/question|title|answer|write|canvas|input|num|op/i.test(t)) {
          els.push(e.tagName+'.'+t.substring(0,40)+' ['+(e.innerText||'').substring(0,20)+']');
        }
      });
      return els.slice(0,40).join('\n');
    })()"""),
    ("canvas 元素", """(function(){
      var cs=document.querySelectorAll('canvas');
      var out=[];
      for(var i=0;i<cs.length;i++){ out.push(i+': size='+cs[i].width+'x'+cs[i].height+' cls='+(cs[i].className||'')); }
      return out.join('\n') || 'no canvas';
    })()"""),
    ("window 上的可疑函数", """(function(){
      var out=[];
      for(var k in window){
        if(typeof window[k]==='function' && /(answer|submit|recogn|hand|write|result|solve|cal|input|tap|click|choice|choose|select|send|emit)/i.test(k)){
          out.push(k);
        }
      }
      return out.slice(0,60).join(',');
    })()"""),
]
for name, js in probes:
    try:
        val = cdp_eval(ws, js)
        print(f"\n=== {name} ===", flush=True)
        print(str(val)[:2500], flush=True)
    except Exception as e:
        print(f"\n=== {name} === ERR {e}", flush=True)
