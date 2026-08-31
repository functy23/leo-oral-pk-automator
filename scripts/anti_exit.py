#!/usr/bin/env python3
"""attach + performNow 快速反退出测试"""
import frida
import subprocess
import sys
import time

PKG = "com.fenbi.android.leo"
ADB = "/opt/homebrew/bin/adb"

JS = r"""
'use strict';
function report(kind, info) {
    send({ type: kind, data: info });
}

function main() {
    // 同步安装, 无延迟
    try {
        var System = Java.use('java.lang.System');
        System.exit.implementation = function (code) {
            report('blocked-System.exit', { code: code });
            // 不退出
        };
        report('ok-System', {});
    } catch (e) { report('err-System', { e: '' + e }); }

    try {
        var Runtime = Java.use('java.lang.Runtime');
        Runtime.exit.implementation = function (code) {
            report('blocked-Runtime.exit', { code: code });
        };
        Runtime.halt.implementation = function (code) {
            report('blocked-Runtime.halt', { code: code });
        };
        report('ok-Runtime', {});
    } catch (e) { report('err-Runtime', { e: '' + e }); }

    try {
        var Process = Java.use('android.os.Process');
        Process.killProcess.implementation = function (pid) {
            report('blocked-killProcess', { pid: pid });
        };
        Process.sendSignal.implementation = function (pid, sig) {
            report('blocked-sendSignal', { pid: pid, sig: sig });
        };
        report('ok-Process', {});
    } catch (e) { report('err-Process', { e: '' + e }); }

    // native 退出
    try {
        var libc = Process.getModuleByName('libc.so');
        ['exit', '_exit', 'exit_group'].forEach(function (name) {
            var p = libc.getExportByName(name);
            if (p) {
                Interceptor.attach(p, {
                    onEnter: function (args) {
                        report('native-' + name, { code: args[0].toInt32() });
                    }
                });
            }
        });
        report('ok-native', {});
    } catch (e) { report('err-native', { e: '' + e }); }
}

Java.performNow(function () {
    main();
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
    print(f"[+] fast anti-exit hooks loaded", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    sess.detach()


if __name__ == "__main__":
    main()
