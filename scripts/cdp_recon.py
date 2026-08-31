#!/usr/bin/env python3
"""CDP 侦察工具: 连接小猿口算 PK WebView, 注入 JS 侦察环境"""
import json
import subprocess
import sys
import time
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
        if "pk" in p.get("url", "") or "口算" in p.get("title", ""):
            return p["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"] if pages else None


def cdp_eval(ws_url, js, timeout=10):
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")
    ws.close()
    return None


def main():
    ws = get_page_ws()
    if not ws:
        print("[!] 未找到 PK 页面", flush=True)
        sys.exit(1)
    print(f"[+] PK page: {ws}", flush=True)

    probes = [
        ("页面标题", "document.title"),
        ("URL", "location.href"),
        ("body 文本前500字", "document.body ? document.body.innerText.substring(0, 500) : 'none'"),
        ("全局键(前60)", "Object.keys(window).filter(k=>k.length<40).slice(0, 60).join(',')"),
        ("Vue 实例", "typeof Vue !== 'undefined' ? 'Vue loaded' : (document.querySelector('#app') ? 'app el exists' : 'no vue')"),
        ("DOM 结构", "(function(){ var r=[]; function walk(el,d){ if(d>4) return; r.push(' '.repeat(d)+el.tagName+(el.className?'.'+String(el.className).split(' ').slice(0,3).join('.'):'')); for(var c of el.children){ walk(c,d+1); } } walk(document.body,0); return r.join('\n').substring(0, 2000); })()"),
    ]
    for name, js in probes:
        try:
            val = cdp_eval(ws, js)
            print(f"\n=== {name} ===", flush=True)
            print(str(val)[:2000], flush=True)
        except Exception as e:
            print(f"\n=== {name} === ERROR: {e}", flush=True)

    # 保持连接一段时间供用户操作
    print("\n[+] 侦察完成. 如需交互式操作请扩展此脚本.", flush=True)


if __name__ == "__main__":
    main()
