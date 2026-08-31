#!/usr/bin/env python3
"""CDP 测试 v25: 提交正确答案!"""
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
                return "ERR:" + str(r.get("description", ""))[:300]
            return r.get("value", "no-value")
    return None

ws = get_page_ws()

# 读取当前答案, 然后提交
js = """(async function(){
  var out = {};
  var m = await System.import('https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js');
  var api = m.d();
  var cfg = api.recognizeConfig.value;
  out.answers = cfg.answers;
  out.questionIndex = cfg.questionIndex;
  // 提交正确答案 (answer=1 正确)
  var result = {
    recognizeResult: cfg.answers[0],
    pathPoints: [],
    answer: 1,
    showReductionFraction: 0
  };
  try {
    api.onRecognize.value(result);
    out.submitted = true;
    out.submittedResult = cfg.answers[0];
  } catch(e) {
    out.submitErr = String(e).substring(0,300);
  }
  return JSON.stringify(out);
})()"""
try:
    val = cdp_eval(ws, js)
    print("=== 提交结果 ===", flush=True)
    print(str(val)[:1500], flush=True)
    time.sleep(2)
    # 看答案区/进度变化
    js2 = """(function(){
      var out = {};
      var blocks = document.querySelectorAll('.answer-block');
      var filled = [];
      for(var i=0;i<blocks.length;i++){
        var t = blocks[i].innerText.trim();
        if(t && t !== '?') filled.push(i+':'+t);
      }
      out.filled = filled.slice(0,8);
      out.bodyText = document.body.innerText.replace(/\n/g,'|').substring(0,200);
      return JSON.stringify(out);
    })()"""
    val2 = cdp_eval(ws, js2)
    print("=== 页面状态 ===", flush=True)
    print(str(val2)[:1000], flush=True)
except Exception as e:
    print("ERR:", e, flush=True)
