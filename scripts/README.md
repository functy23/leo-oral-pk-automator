# 调试/侦察脚本 (开发记录)

> 这些脚本是开发过程中的侦察与调试工具，**仅用于理解应用结构和调试，非主流程所需**。
> 供后续开发者/Agent 参考，理解小猿口算 H5 页面的技术细节。

## 分类

### CDP 侦察系列 (cdp_recon*.py)
通过 DevTools 协议侦察对局页面结构:
- cdp_recon.py → 页面基本信息 (标题/URL/全局对象)
- cdp_recon2.py → Vue 实例/组件树
- cdp_recon5.py → 题目容器 innerHTML (发现 primary-question-wrap)
- cdp_recon6.py → 原生桥对象
- cdp_recon8.py → 回调函数清单 (发现 recognize_callback)
- cdp_recon10.py → recognize 回调源码
- cdp_recon14.py → 识别相关函数/脚本列表
- cdp_recon15.py → 已加载 JS 资源列表
- cdp_recon16.py → SystemJS 模块检查
- cdp_recon17.py → SystemJS 访问模块

### CDP 注入测试 (cdp_test*.py)
验证注入方案:
- cdp_test18/19.py → 构造 base64url 识别结果调用 recognize_callback
- cdp_test20.py → System.import 访问识别模块
- cdp_test22.py → 模拟手写触摸
- cdp_test23.py → System.import 完整 URL (突破点!)
- cdp_test24.py → 读取 recognizeConfig (拿到 answers)
- cdp_test25.py → 提交正确答案 (验证成功!)
- cdp_verify26.py → 提交后页面状态验证

### Frida 侦察 (recon*.py, anti_*.py, spawn_anti.py)
早期 frida 路线 (已弃用 - 应用有反 frida 检测):
- recon.py → WebView 活动侦察
- recon_attach.py → attach 模式
- anti_suicide.py / anti_exit.py → 反退出 hook
- spawn_anti.py → spawn 模式

## 关键结论 (供参考)

1. **识别链路**: 手写 → recognize_callback(base64url) → pt() 解密 → onRecognize
2. **正确答案**: 在前端 recognizeConfig.answers (明文)
3. **模块访问**: System.import('...index-legacy.DMgv2yXx.js') → m.d() 得 API
4. **frida 不可用**: 反检测, 注入即退出 → 用 LSPosed
