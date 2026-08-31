#!/usr/bin/env python3
"""spawn + gating 反退出: 在应用最早阶段注入, hook 所有退出路径, 观察存活"""
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

function hookAllExits() {
    // Java 层
    Java.perform(function () {
        try {
            var Process = Java.use('android.os.Process');
            var kos = Process.killProcess.overloads;
            for (var i = 0; i < kos.length; i++) {
                (function (ov) {
                    ov.implementation = function () {
                        report('blocked-killProcess', { args: [].slice.call(arguments).map(function(a){return ''+a;}) });
                        return;
                    };
                })(kos[i]);
            }
            try {
                Process.sendSignal.implementation = function (pid, sig) {
                    report('blocked-sendSignal', { pid: pid, sig: sig });
                    return;
                };
            } catch (e) {}
        } catch (e) { report('err', { where: 'Process', e: '' + e }); }

        try {
            var System = Java.use('java.lang.System');
            System.exit.implementation = function (code) {
                report('blocked-System.exit', { code: code });
                return;
            };
        } catch (e) { report('err', { where: 'System', e: '' + e }); }

        try {
            var Runtime = Java.use('java.lang.Runtime');
            Runtime.exit.implementation = function (code) {
                report('blocked-Runtime.exit', { code: code });
                return;
            };
            Runtime.halt.implementation = function (code) {
                report('blocked-Runtime.halt', { code: code });
                return;
            };
        } catch (e) { report('err', { where: 'Runtime', e: '' + e }); }

        try {
            var ActivityThread = Java.use('android.app.ActivityThread');
            // 无退出方法, 跳过
        } catch (e) {}

        report('java-exit-hooks-ready', {});
    });

    // native 层
    var libc = Process.getModuleByName('libc.so');
    ['exit', '_exit', 'exit_group', 'abort'].forEach(function (name) {
        try {
            var p = libc.getExportByName(name);
            if (!p) return;
            Interceptor.attach(p, {
                onEnter: function (args) {
                    report('blocked-native-' + name, { code: args[0].toInt32() });
                    // exit_group 无法恢复, 尝试注入死循环防止真正退出?
                }
            });
        } catch (e) {}
    });
    report('native-exit-hooks-ready', {});
}

Java.perform(function () {
    hookAllExits();
    report('ready', {});
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
    print(f"[+] spawned pid={argv}", flush=True)
    sess = dev.attach(argv)
    sc = sess.create_script(JS)
    sc.on("message", on_message)
    sc.load()
    print(f"[+] hooks installed, resuming...", flush=True)
    dev.resume(argv)
    print(f"[+] resumed, monitoring...", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
