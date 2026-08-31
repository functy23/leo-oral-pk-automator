#!/usr/bin/env python3
"""CDP 测试 v19: 多格式注入 + 检查答案区"""
import json, subprocess, urllib.request, websocket, time, base64

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

# 查看答案区当前状态
js0 = """(function(){
  var blocks = document.querySelectorAll('.answer-block');
  var out = [];
  for(var i=0;i<blocks.length;i++){
    out.push(i + ': [' + blocks[i].innerText + '] cls=' + blocks[i].className);
  }
  return JSON.stringify(out);
})()"""
print("答案区:", cdp_eval(ws, js0), flush=True)

# 找 recognize_callback
js1 = "(function(){var ks=Object.keys(window).filter(function(k){return k.indexOf('recognize_callback')>=0});return JSON.stringify(ks)})()"
cb = json.loads(cdp_eval(ws, js1))[-1]
print("callback:", cb, flush=True)

# 测试多种 result 结构
variants = [
    {"recognizeResult": "+", "pathPoints": [], "answer": 1, "showReductionFraction": 0},
    {"recognizeResult": "+", "answer": 1},
    ["+", [], 1, 0],
    {"result": "+", "answer": 1, "recognizeResult": "+", "pathPoints": [{"x":1,"y":1}]},
]
for i, v in enumerate(variants):
    raw = json.dumps(v).encode()
    b64 = base64.b64encode(raw).decode().rstrip("=").replace("+", "-").replace("/", "_")
    js = f"window['{cb}']('{b64}'); 'ok'"
    try:
        cdp_eval(ws, js)
        time.sleep(1)
        state = cdp_eval(ws, js0)
        print(f"[variant {i}] {json.dumps(v)[:80]} -> {state}", flush=True)
    except Exception as e:
        print(f"[variant {i}] ERR {e}", flush=True)
