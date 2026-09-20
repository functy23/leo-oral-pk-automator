<div align="center">

# 🤖 Leo Oral PK Automator

**一个 LSPosed + Chrome DevTools 协议的研究项目，自动化小猿口算 PK 答题 —— 仅供学习 WebView 调试与 Android 逆向。**

[![leo-oral-pk-automator](https://img.shields.io/badge/leo-oral-pk-automator-LEO-orange.svg)](https://github.com/functy23/leo-oral-pk-automator)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Top Language](https://img.shields.io/github/languages/top/functy23/leo-oral-pk-automator?style=flat)](https://github.com/functy23/leo-oral-pk-automator)
[![Platform](https://img.shields.io/badge/platform-Android%20%7C%20LSPosed-lightgrey.svg?logo=android&logoColor=white)](https://github.com/functy23/leo-oral-pk-automator)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)

[![Stars](https://img.shields.io/github/stars/functy23/leo-oral-pk-automator?style=flat&logo=github)](https://github.com/functy23/leo-oral-pk-automator/stargazers)
[![Repo Size](https://img.shields.io/github/repo-size/functy23/leo-oral-pk-automator?style=flat&logo=github)](https://github.com/functy23/leo-oral-pk-automator)
[![Contributors](https://img.shields.io/github/contributors/functy23/leo-oral-pk-automator?color=ee8449&logo=githubsponsors)](https://github.com/functy23/leo-oral-pk-automator/graphs/contributors)

[Issues](https://github.com/functy23/leo-oral-pk-automator/issues) • [AGENTS.md](AGENTS.md)

[English](../README.md) | **简体中文**
</div>

---
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
