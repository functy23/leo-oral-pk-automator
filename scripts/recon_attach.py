#!/usr/bin/env python3
"""反反调试 + 侦察 v4: attach 后立即中和反 Frida 检测, 保持存活, 同时记录 WebView 活动"""
import frida
import subprocess
import sys
import time

PKG = "com.fenbi.android.leo"
ADB = "/opt/homebrew/bin/adb"

JS = r"""
'use strict';

var seen = {};
function report(kind, info) {
    var key = kind + JSON.stringify(info);
    if (seen[key]) return;
    seen[key] = true;
    send({ type: kind, data: info });
}

// ============ 反反调试: 中和自杀 ============
function antiSuicide() {
    // libc 层
    var libc = Process.getModuleByName('libc.so');
    function hook(name, onEnter) {
        try {
            var p = libc.getExportByName(name);
            if (!p) return;
            Interceptor.attach(p, { onEnter: onEnter });
        } catch (e) {}
    }

    // 拦截自杀信号调用
    hook('kill', function (args) {
        var sig = args[1].toInt32();
        if (sig === 9 || sig === 6) {
            report('blocked-kill', { sig: sig });
            args[1] = ptr(0); // 改为 0 信号
        }
    });
    hook('pthread_kill', function (args) {
        var sig = args[1].toInt32();
        if (sig === 9 || sig === 6) {
            report('blocked-pthread_kill', { sig: sig });
            args[1] = ptr(0);
        }
    });
    hook('abort', function () {
        report('blocked-abort', {});
        // 跳到 exit(0) 附近? 直接改返回地址不可靠, 只记录
    });
    hook('exit', function (args) {
        report('blocked-exit', { code: args[0].toInt32() });
        // 阻止正常退出: 挂起线程
        // Thread.sleep 不现实, 仅记录
    });

    // Java 层自杀
    Java.perform(function () {
        try {
            var Process = Java.use('android.os.Process');
            Process.killProcess.implementation = function (pid) {
                report('blocked-killProcess', { pid: pid });
                return; // 吞掉
            };
            Process.myPid.implementation = function () { return 999999; };
        } catch (e) {}
        try {
            var System = Java.use('java.lang.System');
            System.exit.implementation = function (code) {
                report('blocked-System.exit', { code: code });
                return; // 吞掉
            };
        } catch (e) {}
        try {
            var Runtime = Java.use('java.lang.Runtime');
            Runtime.halt.implementation = function (code) {
                report('blocked-Runtime.halt', { code: code });
                return;
            };
        } catch (e) {}
    });
}

// ============ 中和 frida 字符串检测 ============
function neutralizeFridaStrings() {
    var libc = Process.getModuleByName('libc.so');
    function hookStr(name) {
        try {
            var p = libc.getExportByName(name);
            if (!p) return;
            Interceptor.attach(p, {
                onEnter: function (args) {
                    try {
                        var a0 = args[0].readCString();
                        if (a0 && /frida/i.test(a0)) {
                            report('blocked-' + name, { s: a0.substring(0, 80) });
                            args[0] = Memory.allocUtf8String('a'); // 替换为无害字符串
                        }
                    } catch (e) {}
                    try {
                        var a1 = args[1].readCString();
                        if (a1 && /frida/i.test(a1)) {
                            report('blocked-' + name + '-arg1', { s: a1.substring(0, 80) });
                            args[1] = Memory.allocUtf8String('a');
                        }
                    } catch (e) {}
                }
            });
        } catch (e) {}
    }
    hookStr('strstr');
    hookStr('strcmp');
    hookStr('strncmp');
    hookStr('strcasestr');

    // 拦截 /proc/self/maps 等读取中的 frida 特征 - 通过 open 后 read 的内容过滤
    // 更简单: hook read, 过滤内容
    try {
        var readP = libc.getExportByName('read');
        Interceptor.attach(readP, {
            onLeave: function (retval) {
                try {
                    var n = retval.toInt32();
                    if (n > 0 && n < 4096) {
                        var buf = this.context.r1.readUtf8String(n);
                        if (buf && /frida|gum-js-loop|gmain|linjector/i.test(buf)) {
                            // 清空缓冲区的 frida 特征
                            report('blocked-read-frida', {});
                            var m = Memory.alloc(n);
                            m.writeUtf8String(buf.replace(/frida|gum-js-loop|gmain|linjector/gi, 'xxxxx'));
                            this.context.r1 = m;
                        }
                    }
                } catch (e) {}
            }
        });
    } catch (e) {}
}

// ============ WebView 侦察 ============
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
    antiSuicide();
    neutralizeFridaStrings();
    hookWebview('android.webkit.WebView');
    hookWebview('com.tencent.smtt.sdk.WebView');
    report('ready', {});
});
"""


def on_message(msg, data):
    if msg.get("type") == "send":
        p = msg["payload"]
        print(f"[{p['type']}] {p['data']}", flush=True)
    elif msg.get("type") == "error":
        print(f"[script-error] {msg.get('description')}", flush=True)


def get_pid():
    out = subprocess.check_output([ADB, "shell", "pidof", PKG]).decode().strip()
    if out:
        return int(out.split()[0])
    return None


def main():
    pid = get_pid()
    if not pid:
        print("[!] 应用未运行, 请先打开小猿口算", flush=True)
        sys.exit(1)
    print(f"[+] attaching pid={pid}", flush=True)
    dev = frida.get_usb_device(timeout=10)
    sess = dev.attach(pid)
    sc = sess.create_script(JS)
    sc.on("message", on_message)
    sc.load()
    print(f"[+] script loaded (anti-frida + webview recon)", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    sess.detach()


if __name__ == "__main__":
    main()
