#!/usr/bin/env python3
"""CDP 测试 v22: 模拟手写触摸"""
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

# 1. 找 canvas (手写板)
js0 = """(function(){var cs=document.querySelectorAll('canvas');var out=[];for(var i=0;i<cs.length;i++){var r=cs[i].getBoundingClientRect();out.push(i+': '+cs[i].width+'x'+cs[i].height+' rect='+Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+'x'+Math.round(r.height)+' cls='+(cs[i].className||''));}return JSON.stringify(out)})()"""
print("canvas:", cdp_eval(ws, js0), flush=True)

# 2. 模拟在 canvas 上画一笔 (touchstart/move/end)
js1 = """(function(){
  var cs = document.querySelectorAll('canvas');
  if(!cs.length) return 'no canvas';
  var c = cs[0];
  var r = c.getBoundingClientRect();
  var cx = r.x + r.width/2, cy = r.y + r.height/2;
  function ev(type, x, y){
    var e = new TouchEvent(type, {touches:[new Touch({identifier:1, target:c, clientX:x, clientY:y, pageX:x, pageY:y})], bubbles:true, cancelable:true});
    c.dispatchEvent(e);
  }
  ev('touchstart', cx-20, cy-20);
  ev('touchmove', cx, cy);
  ev('touchmove', cx+20, cy+20);
  ev('touchend', cx+20, cy+20);
  return 'drawn';
})()"""
print("模拟手写:", cdp_eval(ws, js1), flush=True)
time.sleep(3)
# 看答案区变化
js2 = """(function(){var blocks=document.querySelectorAll('.answer-block');var out=[];for(var i=0;i<blocks.length;i++){if(blocks[i].innerText.trim()){out.push(i+':['+blocks[i].innerText.trim()+']');}}return JSON.stringify(out.slice(0,10))})()"""
print("答案区变化:", cdp_eval(ws, js2), flush=True)
