#!/usr/bin/env python3
"""侦察脚本 v2: gating 模式跟随所有子进程, 记录 H5 容器活动"""
import frida
import sys
import time

PKG = "com.fenbi.android.leo"

JS = r"""
'use strict';
var seen = {};

function report(kind, info) {
    var key = kind + JSON.stringify(info);
    if (seen[key]) return;
    seen[key] = true;
    send({ type: kind, data: info });
}

function hookWebview(clsName) {
    var C;
    try { C = Java.use(clsName); } catch (e) { return; }
    report('present', { cls: clsName });

    try {
        var overloads = C.loadUrl.overloads;
        for (var i = 0; i < overloads.length; i++) {
            (function (ov) {
                ov.implementation = function () {
                    report('loadUrl', { cls: clsName, arg0: '' + arguments[0] });
                    return ov.apply(this, arguments);
                };
            })(overloads[i]);
        }
    } catch (e) {}

    try {
        var o2 = C.addJavascriptInterface.overloads;
        for (var k = 0; k < o2.length; k++) {
            (function (ov) {
                ov.implementation = function (obj, name) {
                    var methods = [];
                    try {
                        var m = obj.getClass().getMethods();
                        for (var q = 0; q < m.length; q++) {
                            if (m[q].getAnnotation(Java.use('android.webkit.JavascriptInterface'))) {
                                var ps = m[q].getParameterTypes();
                                var sig = [];
                                for (var p = 0; p < ps.length; p++) sig.push('' + ps[p].getName());
                                methods.push(m[q].getName() + '(' + sig.join(',') + ')');
                            }
                        }
                    } catch (e2) {}
                    report('addJsInterface', { cls: clsName, name: '' + name,
                        objClass: obj ? obj.getClass().getName() : 'null', methods: methods });
                    return ov.apply(this, arguments);
                };
            })(o2[k]);
        }
    } catch (e) {}

    try {
        var o4 = C.evaluateJavascript.overloads;
        for (var w = 0; w < o4.length; w++) {
            (function (ov) {
                ov.implementation = function (js) {
                    var s = '' + js;
                    if (s.length > 300) s = s.substring(0, 300) + '...';
                    report('evaluateJS', { cls: clsName, js: s });
                    return ov.apply(this, arguments);
                };
            })(o4[w]);
        }
    } catch (e) {}
}

Java.perform(function () {
    hookWebview('android.webkit.WebView');
    hookWebview('com.tencent.smtt.sdk.WebView');
});
"""


def on_message(msg, data):
    if msg.get("type") == "send":
        p = msg["payload"]
        print(f"[{p['type']}] {p['data']}", flush=True)
    elif msg.get("type") == "error":
        print(f"[script-error] {msg.get('description')}", flush=True)


def main():
    dev = frida.get_usb_device(timeout=10)
    argv = dev.spawn([PKG])
    print(f"[+] spawn gating pid={argv}", flush=True)

    sessions = []

    def load_script(pid):
        sess = dev.attach(pid)
        sc = sess.create_script(JS)
        sc.on("message", on_message)
        sc.load()
        sessions.append((sess, sc))
        print(f"[+] script loaded into pid={pid}", flush=True)

    # 主进程先注入, resume 后监听子进程
    load_script(argv)

    # Child gating: 所有 fork 出的子进程暂停, 注入后再放行
    dev.enable_child_gating(argv)
    dev.resume(argv)

    def on_child_added(child):
        print(f"[child] pid={child.pid} path={getattr(child, 'path', '?')}", flush=True)
        try:
            load_script(child.pid)
            dev.resume_child(child.pid)
        except Exception as e:
            print(f"[!] child inject fail: {e}", flush=True)
            try:
                dev.resume_child(child.pid)
            except Exception:
                pass

    dev.on("child-added", on_child_added)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
