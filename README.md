# 小猿口算 PK 自动答题 (leo-oral-pk-automator)

> 仅供学习 WebView 调试 / Android 逆向 / 自动化技术。
> 使用自动化工具参与在线 PK 违反平台用户协议，可能导致账号封禁。请勿用于作弊。

基于 **LSPosed 模块 + Chrome DevTools 协议 (CDP)** 的自动化脚本。

## 依赖模块（必须配合）

本仓库需要配合 LSPosed 模块仓库使用:
https://github.com/functy23/leo-webview-debugger

1. 安装模块 APK
2. LSPosed 启用, 作用域勾选 com.fenbi.android.leo
3. 运行 pk_auto.py

## 使用

pip install websocket-client
python3 pk_auto.py

启动交互: 最低/最高延迟(回车用默认 0.01-0.03), 循环局数(0=无限)

## 文件

- pk_auto.py 主脚本
- pk_watch.py / pk_netwatch.py / pk_tracewatch.py 调试工具
- scripts/ 开发期侦察脚本
- AGENTS.md AI 开发指南

## License

MIT
