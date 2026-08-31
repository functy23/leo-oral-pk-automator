#!/usr/bin/env python3
"""反反调试 v2: 简化 hook, 只中和自杀调用, 去掉危险的 read hook"""
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

function antiSuicide() {
    var libc = Process.getModuleByName('libc.so');
    var targets = ['kill', 'pthread_kill', 'tgkill', 'raise', 'abort', 'exit', '_exit', 'exit_group'];
    targets.forEach(function (name) {
        try {
            var p = libc.getExportByName(name);
            if (!p) return;
            Interceptor.attach(p, {
                onEnter: function (args) {
                    var sig = -1;
                    try {
                        if (name === 'kill' || name === 'pthread_kill' || name === 'tgkill' || name === 'raise') {
                            // kill(pid, sig): args[1]; tgkill(tid, tid, sig): args[2]; raise(sig): args[0]
                            if (name === 'tgkill') sig = args[2].toInt32();
                            else if (name === 'raise') sig = args[0].toInt32();
                            else sig = args[1].toInt32();
                            if (sig === 9 || sig === 6 || sig === 4) {
                                report('blocked-' + name, { sig: sig });
                                if (name === 'raise') args[0] = ptr(0);
                                else if (name === 'tgkill') args[2] = ptr(0);
                                else args[1] = ptr(0);
                            }
                        } else {
                            report('blocked-' + name, { code: args[0].toInt32() });
                            // 无法阻止, 记录即可
                        }
                    } catch (e) {}
                }
            });
        } catch (e) {}
    });

    Java.perform(function () {
        try {
            var Process = Java.use('android.os.Process');
            Process.killProcess.implementation = function (pid) {
                report('blocked-killProcess', { pid: pid });
                return;
            };
        } catch (e) {}
        try {
            var System = Java.use('java.lang.System');
            System.exit.implementation = function (code) {
                report('blocked-System.exit', { code: code });
                return;
            };
        } catch (e) {}
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
        } catch (e) {}
    });
}

Java.perform(function () {
    antiSuicide();
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
        print("[!] 应用未运行", flush=True)
        sys.exit(1)
    print(f"[+] attaching pid={pid}", flush=True)
    dev = frida.get_usb_device(timeout=10)
    sess = dev.attach(pid)
    sc = sess.create_script(JS)
    sc.on("message", on_message)
    sc.load()
    print(f"[+] anti-suicide script loaded", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    sess.detach()


if __name__ == "__main__":
    main()
