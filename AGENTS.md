# AGENTS.md — AI 开发指南 (leo-oral-pk-automator)

> **拼写确认**: 本文件名为 AGENTS.md（不是 AGNETS.md / Agent.md）。
> 本文件为 AI 编码助手提供本项目完整工作上下文。
> **任何修改、扩展、调试本项目前，必须完整阅读本文件。**

---

## 0. 项目一句话

通过 **LSPosed 模块强制开启 WebView 调试** + **Chrome DevTools 协议 (CDP) 注入 JavaScript**，
在**主机端**用 Python 驱动手机上的小猿口算 App 自动完成 PK 对局（读答案 → 提交 → 结算 → 领经验 → 无限下一局）。

**双仓库架构（必须配合使用）**：

| 仓库 | 作用 |
|------|------|
| leo-oral-pk-automator（本仓库） | 主机端 Python 主脚本 + 调试工具 |
| leo-webview-debugger（配套仓库） | 设备端 LSPosed 模块，强制开启 WebView 调试 |

---

## 1. 系统架构总览

```
┌────────────────────── 设备端 (Android, root) ──────────────────────┐
│  LSPosed 模块 (leo-webview-debugger)                               │
│    hook Activity.onCreate → WebView.setWebContentsDebuggingEnabled(true) │
│    → WebView devtools 端口: localabstract:webview_devtools_remote_<pid> │
│  小猿口算 App (com.fenbi.android.leo)                              │
│    PK 对局页 = H5 Vue SPA (SystemJS 模块化)                         │
│    URL: xyks.yuanfudao.com/bh5/leo-web-oral-pk/*.html              │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ adb forward tcp:9333 → localabstract:...
                               ▼
┌────────────────────── 主机端 (macOS/Linux) ────────────────────────┐
│  pk_auto.py (Python 3.10+)                                         │
│    CDP WebSocket 连接 → Runtime.evaluate 注入 JS                    │
│    读 recognizeConfig.answers (答案) → onRecognize 提交             │
│    页面状态机: exercise → result → honor → pk 循环                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. 环境与依赖

### 设备端
| 组件 | 要求 | 备注 |
|------|------|------|
| 手机 | Android, 已 root | 实测机型 OPPO PGCM10 (arm64) |
| Magisk | + Zygisk | LSPosed 依赖 |
| LSPosed | 已安装 | 实测为 corepatch 衍生版 (org.lsposed.corepatch) |
| LSPosed 模块 | leo-webview-debugger 的 APK | 作用域必须勾选 com.fenbi.android.leo |
| 小猿口算 | 已安装并登录 | 包名 com.fenbi.android.leo |

### 主机端
| 组件 | 要求 |
|------|------|
| Python | 3.10+ (实测 3.14) |
| pip 包 | websocket-client (pip install websocket-client --break-system-packages) |
| adb | 已连接设备 (adb devices 可见) |
| adb 路径 | 默认 /opt/homebrew/bin/adb (macOS)，Linux 需改 ADB 常量 |

---

## 3. 文件清单

| 文件 | 角色 | 修改频率 |
|------|------|---------|
| pk_auto.py | 主脚本（唯一核心） | 高 |
| pk_watch.py | 调试：实时状态监控 | 低 |
| pk_netwatch.py | 调试：抓取答题网络请求 (CDP Network 域) | 低 |
| pk_tracewatch.py | 调试：观察手写轨迹 (writeContent ref) | 低 |
| scripts/ | 开发期侦察脚本（Frida 早期路线已弃用；CDP 侦察/注入测试参考） | 只读参考 |
| scripts/README.md | 侦察脚本用途说明 + 逆向结论 | 只读 |
| README.md | 用户使用说明 | 中 |

---

## 4. pk_auto.py 代码解剖（逐函数）

### 4.1 常量

```python
ADB = "/opt/homebrew/bin/adb"        # adb 路径 (Linux 需改)
PKG = "com.fenbi.android.leo"         # 目标应用包名
ORAL_MODULE = "https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js"
                                      # 识别核心模块 (SystemJS), 硬编码, 前端发版会变!
FORWARD_PORT = 9333                    # adb forward 端口
MIN_DELAY = 0.01                       # 最低答题延迟 (秒)
MAX_DELAY = 0.03                       # 最高答题延迟 (秒)
ACCURACY = 1.0                         # 正确率 (全对模式)
MAX_ROUNDS = 0                         # 0=无限循环; >0=跑N局后停
LOG_FILE = "/tmp/pk_auto.log"          # 日志文件
```

### 4.2 交互配置
- setup_delay() — 启动时读入最低/最高延迟（回车用默认；支持 8 位小数；自动交换 min/max）
- setup_rounds() — 启动时读入循环局数（0 或负数 = 无限）

### 4.3 基础设施
- log(msg) — 终端 + LOG_FILE 双写（带时间戳）
- class CDP — WebSocket 客户端
  - eval(js, timeout) — 发 Runtime.evaluate（returnByValue + awaitPromise），取 result.result.value；错误返回 None
  - 注意：id 恒为 1，循环读到 id==1 才返回（无并发请求）
- get_pages() — 核心网络层
  1. adb shell pidof com.fenbi.android.leo（**必须 try/except**，应用被杀时 pidof 返回非 0 → 返回 [] 继续等）
  2. adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>
  3. GET http://127.0.0.1:9333/json → DevTools 页面列表

### 4.4 页面分类（关键）
- classify_page(pages) → dict:
  - exercise: 对局页 (URL 含 exercise) — **答题**
  - result: 结算页 (URL 含 result) — **点继续PK**
  - honor / honor_list: 荣誉榜页 (URL 含 honor-roll, 注意域名是 leo-web-study-group 不是 leo-web-oral) — **领经验**
  - pk: PK 主页 (URL 含 pk) — **点1v1PK开始匹配**
- find_game_page(pages) — 优先级 exercise > result > honor > pk（主循环实际用 classify_page 直接判断）

### 4.5 答题核心
- read_answer(cdp) — 注入 JS:
  1. System.import(ORAL_MODULE) 拿识别模块
  2. m.d() 得 API
  3. api.recognizeConfig.value → 取 {answers, questionIndex}
  4. document.querySelector('.primary-question:not([style*="none"])') 取当前题文本
  - 返回 {state, answers, questionIndex, q1}；无答案返回 state:'no-config'
- gen_path_points(text) — **模拟手写轨迹**（防风控关键）:
  - '>' / '<': 2 笔斜线（每笔 10-18 点，浮点坐标）
  - 其他: 1 笔弧线
- submit_answer(cdp, text, is_correct) — 提交:
  1. api.writeContent.value = 模拟轨迹（让前端认为有真实手写）
  2. 构造 {recognizeResult, pathPoints, answer: 1/0, showReductionFraction: 0}
  3. api.onRecognize.value(result) → 前端记分推进
- pick_answer(answers) — 全对：取 answers[0]

### 4.6 页面操作
- click_continue(cdp) — 结算页点"继续PK"（优先 .retry 类，兜底文本匹配）
- click_start_match(cdp) — 主页点"1v1PK"（兜底"开始PK"）
- click_claim_exp(cdp) — 领经验点"开心收下"（.btn-confirm-wrap，**故意不做 offsetParent 可见性判断**——弹窗动画期间会误判）

### 4.7 主循环状态机（main()）— 本项目最重要的逻辑

每轮:
  1. get_pages() (容错, 应用不在→sleep 2s)
  2. classify_page()
  3. 页面选择优先级:
     exercise 存在 → 答题
     否则 未处理 honor 存在 → 领经验
     否则 result → 点继续PK
     否则 pk → 点1v1PK
  4. 按 page_kind 分发处理

**状态机细节（务必理解，改错会导致死循环）**:

| 状态 | 动作 | 节流 |
|------|------|------|
| exercise + 有答案 | sleep(random(min,max)) → submit_answer → 记分 | 同一题(qi)且 3s 内不重提 |
| exercise + 无答案 | sleep 0.5 (出题前/匹配中) | — |
| result | 若 in_round: 局数+1, 打印完成, 重置; 点继续PK | 距上次提交 >3s |
| honor | 遍历 honor_list 点开心收下; 无论是否点到都标记 processed_honor (防死循环); 未点到重试一次(等2s) | 距上次提交 >1.5s |
| pk | 点1v1PK | 距上次提交 >2s |

**已踩过的坑（改动时不要重蹈）**:
1. **honor 页领完不关闭** → 必须 URL 去重 (processed_honor set)，且点不到按钮也要标记，否则死循环
2. **honor 优先级不能高于 exercise** → 否则对局进行中脚本困在 honor 分支不答题
3. **get_pages 必须容错** → 应用重启/被杀时 pidof 抛异常，不 try 则脚本崩溃退出
4. **重复提交** → 提交后同题 3s 节流，避免一题提交多次（服务端记录异常）
5. **答题延迟** → 默认 0.01-0.03s（用户要求极速）；服务端 costTime 会记录，但实测模拟轨迹后极速也不触发风控

---

## 5. 逆向知识（靶机侧，改脚本前必读）

### 5.1 H5 对局页结构
- 页面: xyks.yuanfudao.com/bh5/leo-web-oral-pk/ 下的 exercise.html(对局) / result.html(结算) / pk.html(主页)
- 经验弹窗页: leo-web-study-group/motivation-honor-roll.html（注意不同路径段）
- 前端框架: Vue 2 + Vite legacy + SystemJS（System.register 模块化）
- 题目容器: #primary-question-wrap / #second-question-wrap（主/副题）
- 题目 DOM: .primary-question:not([style*="none"]) → .common-content(操作数) + .answer-block.circle(答案区)

### 5.2 识别/答题链路（从手写到提交）

```
手写 → 原生识别引擎 → window.recognize_callback_<ts>_<id>(base64url(JSON))
  → pt(t) 解密 (base64url→base64→new Buffer(...).toString())
  → JSON.parse → e.apply(null, result)
  → 前端 At() 构造 {recognizeResult, pathPoints, answer: Ot(t)?1:0, showReductionFraction}
  → api.onRecognize.value(result) → 显示答案 + 记分 + 推进
```

### 5.3 识别模块 API（核心突破口）

```javascript
const m = await System.import('https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js');
const api = m.d();
api.recognizeConfig.value   // { show, scratchPaperEnable, ruleType, keypointId, top, answers: [...正确答案], questionIndex }
api.onRecognize.value       // 识别结果回调 — 提交答案的入口
api.writeContent.value      // 手写轨迹 ref (数组: [stroke][point]={x,y}) — 模拟轨迹写入点
api.setOnRecognize(cfg, cb) // 注册识别配置+回调 (内部调用)
api.pad                    // 手写板状态
api.resetCanvas()          // 清空画布
```

**答案在 recognizeConfig.answers，明文下发，直接读取即可。**

### 5.4 风控规避（实测结论）
- **pathPoints 必须非空** — 空轨迹 = 秒答特征 = 服务端判定作弊（成绩作废）
- **模拟轨迹足够** — 写入 writeContent + pathPoints 后，0.01-0.03s/题极速也不被检测（实测胜场正常+）
- 正确率 100% 不触发风控（实测）——但如需拟人可调 ACCURACY
- 每题只提交一次

---

## 6. 调试工具用法

| 脚本 | 用途 | 关键输出 |
|------|------|---------|
| pk_watch.py | 观察手动答题时的状态变化 | 题目/轨迹/答案区/心跳 |
| pk_netwatch.py | 抓答题 POST 请求 | Network.requestWillBeSent (答题提交加密) |
| pk_tracewatch.py | 记录手写轨迹结构 | strokes/首笔坐标 |

---

## 7. 常见问题排查表

| 症状 | 根因 | 解法 |
|------|------|------|
| 启动后一直"未找到页面" | 应用没开 / devtools 端口没出现 | 确认模块已启用+作用域勾选; 重启应用; ls /dev/socket 或 cat /proc/net/unix | grep webview |
| 脚本崩溃退出 (CalledProcessError) | get_pages 未容错(旧版) | 确认 try/except 存在 |
| 卡在 honor 不答题 | honor 优先级高于 exercise | 检查页面选择逻辑 |
| 一直点"继续PK" | 点击后没进下一局 / 按钮选择器失效 | 检查 .retry 类 / 文本匹配 |
| 经验领不到 | 弹窗动画未完成 | 已加重试(等2s), 确认 click_claim_exp 存在 |
| 对局没自动开始 | 主页没点 1v1PK | 检查 click_start_match |
| 答题但服务端记录 0 题 | recognizeConfig 读取失败 | 手动验证 System.import 模块 URL 是否变更 |
| **模块 URL 变更** | 前端发版改了 chunk hash | **重新抓取 assets 列表 (见下)** |

---

## 8. 前端发版时的适配流程（重要）

ORAL_MODULE 的 chunk 文件名带 hash（如 index-legacy.DMgv2yXx.js），**前端发版后 hash 会变**，脚本会失效。适配步骤：

1. 进入对局页后抓资源列表:
   ```javascript
   // CDP Runtime.evaluate
   performance.getEntriesByType('resource').map(e=>e.name).filter(n=>/\\.js/.test(n))
   ```
2. 找到新的 index-legacy.XXXX.js（识别模块）URL，更新 ORAL_MODULE
3. 验证 m.d() 的 API keys 是否变化（recognizeConfig / onRecognize / writeContent）

---

## 9. 代码规范与注意事项

- **内嵌 JS 字符串**：用 %(...)s 格式化注入变量；JS 内字符串用 JSON.stringify 转义（如答案可能是中文/符号）
- **CDP eval 的 JS**：避免裸反斜杠/换行导致 SyntaxError；复杂输出用 JSON.stringify 返回
- **Python 语法**：global MIN_DELAY, MAX_DELAY 在 setup 函数内修改模块常量时必须声明
- **日志**：所有关键状态用 log() 输出（终端+文件），方便排查
- **兼容性**：ADB 路径、python3 解释器版本因机器而异（README 已注明）

---

## 10. 扩展方向（未来可能的开发任务）

- [ ] 支持 8 人 PK（多人混战模式，识别 matching-bottom / 排名逻辑）
- [ ] 巅峰对决模式（triggerPeakMatch=1 参数相关）
- [ ] 自动识别"对局结束原因"（胜利/失败/被作废）并在日志区分
- [ ] 支持多设备（adb 多端口 forward 并发）
- [ ] 命令行参数化（argparse 替代交互 input，便于无人值守）
- [ ] 前端 chunk hash 自动发现（抓 resources 自动更新 ORAL_MODULE）

---

## 11. 禁止事项

- 本项目仅限学习研究 WebView 调试 / Xposed 开发 / CDP 注入技术
- 禁止用于作弊、牟利、传播；使用者自行承担账号风险
- 不提供任何账号、token、真实用户数据
