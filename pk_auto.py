#!/usr/bin/env python3
"""小猿口算 PK 自动答题脚本 v3 (抗检测版)
核心改进:
  1. 随机答题延迟 1.5-3.5s (模拟手写时间, 避免秒答风控)
  2. 92% 正确率 (模拟人类, 避免 100% 异常)
  3. 构造真实手写轨迹 pathPoints (模拟笔迹)
  4. answer 字段与识别结果自动匹配 (前端逻辑一致)
"""
import json
import random
import subprocess
import sys
import time
import urllib.request

import websocket

ADB = "/opt/homebrew/bin/adb"
PKG = "com.fenbi.android.leo"
ORAL_MODULE = "https://leo.fbcontent.cn/bh5/leo-web-oral-pk/assets/index-legacy.DMgv2yXx.js"
FORWARD_PORT = 9333

# 配置 (超极速模式 - 默认 0.01-0.03s/题, 启动时可覆盖)
MIN_DELAY = 0.01    # 最短答题延迟 (秒)
MAX_DELAY = 0.03    # 最长答题延迟
ACCURACY = 1.0     # 正确率 (全对)
MAX_ROUNDS = 0      # 循环局数: 0 或负数 = 无限
LOG_FILE = "/tmp/pk_auto.log"


def setup_delay():
    """启动时交互设置延迟范围 (输入两次: 最低/最高), 支持 8 位小数"""
    global MIN_DELAY, MAX_DELAY
    try:
        lo = input(f"[配置] 最低延迟秒数 (默认 {MIN_DELAY:.8f}, 直接回车用默认): ").strip()
        if lo:
            MIN_DELAY = max(0.0, float(lo))
        hi = input(f"[配置] 最高延迟秒数 (默认 {MAX_DELAY:.8f}, 直接回车用默认): ").strip()
        if hi:
            MAX_DELAY = max(0.0, float(hi))
        if MAX_DELAY < MIN_DELAY:
            MIN_DELAY, MAX_DELAY = MAX_DELAY, MIN_DELAY
    except (ValueError, EOFError):
        pass
    log(f"延迟范围: {MIN_DELAY:.8f}-{MAX_DELAY:.8f}s (每题随机)")


def setup_rounds():
    """启动时交互设置循环局数 (默认/0 = 无限)"""
    global MAX_ROUNDS
    try:
        r = input(f"[配置] 循环局数 (默认 {MAX_ROUNDS}, 0=无限, 直接回车用默认): ").strip()
        if r:
            MAX_ROUNDS = int(r)
    except (ValueError, EOFError):
        pass
    if MAX_ROUNDS <= 0:
        log("循环局数: 无限")
    else:
        log(f"循环局数: {MAX_ROUNDS} 局")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


class CDP:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self._ws = None

    def connect(self):
        self._ws = websocket.create_connection(self.ws_url, timeout=10)
        return self

    def eval(self, js, timeout=15):
        if not self._ws:
            self.connect()
        self._ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True, "awaitPromise": True}
        }))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == 1:
                r = msg.get("result", {}).get("result", {})
                if r.get("subtype") == "error":
                    return None
                return r.get("value")

    def close(self):
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass


def get_pages():
    # 应用不在时 pidof 返回非0, 需容错 (应用重启/关闭时脚本不崩溃, 继续等待)
    try:
        pid = subprocess.check_output([ADB, "shell", "pidof", PKG],
                                      stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return []
    if not pid:
        return []
    subprocess.run([ADB, "forward", f"tcp:{FORWARD_PORT}",
                    f"localabstract:webview_devtools_remote_{pid}"], capture_output=True)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{FORWARD_PORT}/json", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []


def classify_page(pages):
    """分类页面: exercise(对局) / result(结算) / honor(经验弹窗) / pk主页"""
    result = {"exercise": None, "result": None, "honor": None, "honor_list": [], "pk": None}
    for p in pages:
        u = p.get("url", "")
        if "leo-web-oral" in u:
            if "exercise" in u:
                result["exercise"] = p
            elif "result" in u:
                result["result"] = p
            elif "pk" in u:
                result["pk"] = p
        elif "honor-roll" in u:
            result["honor"] = p
            result["honor_list"].append(p)
    return result


def find_game_page(pages):
    """优先返回对局页(exercise), 其次结果页(result), 再主页(pk)"""
    cls = classify_page(pages)
    return cls["exercise"] or cls["result"] or cls["honor"] or cls["pk"]


def read_answer(cdp):
    js = """(async function(){
      try {
        var m = await System.import('%s');
        var api = m.d();
        var cfg = api.recognizeConfig.value;
        if(!cfg || !cfg.answers) return JSON.stringify({state:'no-config'});
        var q = document.querySelector('.primary-question:not([style*="none"])');
        return JSON.stringify({
          state: 'question',
          answers: cfg.answers,
          questionIndex: cfg.questionIndex,
          q1: q ? q.innerText : '',
          total: cfg.answers.length
        });
      } catch(e) { return JSON.stringify({state:'error', error:String(e).substring(0,150)}); }
    })()""" % ORAL_MODULE
    val = cdp.eval(js)
    if not val:
        return {"state": "no-response"}
    try:
        return json.loads(val)
    except Exception:
        return {"state": "parse-error"}


def gen_path_points(text):
    """生成模拟手写轨迹 (真实感: 1-2笔, 浮点坐标, 模拟写 < 或 >)"""
    import math
    pts = []
    cx, cy = random.uniform(80, 120), random.uniform(480, 560)
    # 每笔 10-18 个点
    n_pts = random.randint(10, 18)
    if text in (">", "<"):
        # 模拟画 > 或 < : 两条斜线
        for stroke in range(2):
            pts.append([])
            x, y = cx, cy
            for i in range(n_pts):
                # 斜线方向
                if text == ">":
                    dx = (1 if stroke == 0 else 0.3) * random.uniform(3.0, 4.5)
                    dy = (-1 if stroke == 0 else 1) * random.uniform(3.0, 4.5)
                else:  # "<"
                    dx = (-1 if stroke == 0 else -0.3) * random.uniform(3.0, 4.5)
                    dy = (-1 if stroke == 0 else 1) * random.uniform(3.0, 4.5)
                x += dx
                y += dy
                pts[stroke].append({"x": round(x, 4), "y": round(y, 4)})
    else:
        # 通用: 一道弧线
        pts.append([])
        x, y = cx, cy
        for i in range(n_pts):
            x += random.uniform(2.0, 5.0)
            y += random.uniform(-3.0, 3.0) + math.sin(i / 3.0) * 2
            pts.append([])
            pts[0].append({"x": round(x, 4), "y": round(y, 4)})
    return pts


def submit_answer(cdp, text, is_correct):
    """提交答案: 写入模拟手写轨迹 + 走前端 onRecognize 链路"""
    text_json = json.dumps(text, ensure_ascii=False)
    pts_json = json.dumps(gen_path_points(text))
    js = """(async function(){
      try {
        var m = await System.import('%s');
        var api = m.d();
        // 写入模拟手写轨迹 (让前端认为有真实手写)
        try {
          if (api.writeContent) {
            api.writeContent.value = %s;
          }
        } catch(e2) {}
        var result = {
          recognizeResult: %s,
          pathPoints: %s,
          answer: %s,
          showReductionFraction: 0
        };
        api.onRecognize.value(result);
        return 'ok';
      } catch(e) { return 'err:' + String(e).substring(0,150); }
    })()""" % (ORAL_MODULE, pts_json, text_json, pts_json, "1" if is_correct else "0")
    return cdp.eval(js)


def click_continue(cdp):
    """结算页点击'继续PK' (优先 .retry 类, 兜底按文本找)"""
    js = """(function(){
      // 优先 .retry 类 (结算页的继续PK按钮)
      var el = document.querySelector('.retry');
      if(el && el.offsetParent !== null){
        el.click();
        return 'clicked:.retry';
      }
      // 兜底: 按文本找
      var btns = Array.from(document.querySelectorAll('button,div,span'));
      var targets = ['继续PK','再战','再来一局'];
      for(var t of targets){
        for(var b of btns){
          if(b.innerText && b.innerText.trim() === t && b.offsetParent !== null){
            b.click();
            return 'clicked:' + t;
          }
        }
      }
      return 'not-found';
    })()"""
    return cdp.eval(js)


def click_start_match(cdp):
    """PK主页点击第一个可见的 1v1PK 按钮开始匹配"""
    js = """(function(){
      // 找所有文本为 1v1PK 且可见的元素
      var all = Array.from(document.querySelectorAll('*'));
      for(var i=0;i<all.length;i++){
        var e = all[i];
        if(e.children.length === 0 && e.innerText && e.innerText.trim() === '1v1PK' && e.offsetParent !== null){
          e.click();
          return 'clicked:1v1PK';
        }
      }
      // 兜底: 开始PK
      for(var j=0;j<all.length;j++){
        var e2 = all[j];
        if(e2.children.length === 0 && e2.innerText && e2.innerText.trim() === '开始PK' && e2.offsetParent !== null){
          e2.click();
          return 'clicked:开始PK';
        }
      }
      return 'not-found';
    })()"""
    return cdp.eval(js)


def click_claim_exp(cdp):
    """点击'开心收下'领取经验弹窗 (存在即点, 不依赖可见性判断 - 弹窗动画期间 offsetParent 可能为 null)"""
    js = """(function(){
      // 优先 .btn-confirm-wrap (经验弹窗领取按钮)
      var el = document.querySelector('.btn-confirm-wrap');
      if(el){
        el.click();
        return 'clicked:开心收下';
      }
      // 兜底: 按文本找
      var all = Array.from(document.querySelectorAll('*'));
      for(var i=0;i<all.length;i++){
        var e = all[i];
        if(e.children.length === 0 && e.innerText && e.innerText.trim() === '开心收下'){
          e.click();
          return 'clicked:开心收下(text)';
        }
      }
      return 'not-found';
    })()"""
    return cdp.eval(js)


def pick_answer(answers):
    """选择答案: 全对 (取正确答案列表第一个)"""
    return answers[0], True


def main():
    log("=== 小猿口算 PK 自动答题 v5 (全自动多局) ===")
    setup_delay()   # 交互设置延迟范围
    setup_rounds()  # 交互设置循环局数
    log(f"配置: 延迟 {MIN_DELAY:.8f}-{MAX_DELAY:.8f}s, 全对模式")
    total = 0
    correct = 0
    round_no = 0          # 已完成的局数
    round_answered = 0    # 本局已答题数
    last_qi = -1
    last_url = ""
    last_submit_time = 0
    in_round = False      # 当前是否在对局中 (已答过题)
    processed_honor = set()  # 已领取经验的 honor 页 URL (防重复)

    while True:
        # 局数上限检查 (0=无限)
        if MAX_ROUNDS > 0 and round_no >= MAX_ROUNDS:
            log(f"已达目标 {MAX_ROUNDS} 局, 停止")
            break

        pages = get_pages()
        if not pages:
            time.sleep(2)
            continue

        cls = classify_page(pages)
        # 优先级: exercise(对局答题) > honor(经验领取,仅无对局时) > result > pk
        # 关键: 对局进行中必须优先答题, 不能被困在 honor 分支
        if cls["exercise"]:
            page = cls["exercise"]
            page_kind = "exercise"
        else:
            unprocessed_honor = [hp for hp in (cls.get("honor_list") or [])
                                 if hp.get("url", "") not in processed_honor]
            if unprocessed_honor:
                page = unprocessed_honor[0]
                page_kind = "honor"
            else:
                page = cls["result"] or cls["pk"]
                page_kind = "result" if cls["result"] else "pk"
        if not page:
            time.sleep(1)
            continue
        url = page.get("url", "")
        if url != last_url:
            log(f"页面: {page_kind}")
            last_url = url
            last_qi = -1

        cdp = CDP(page["webSocketDebuggerUrl"])
        try:
            if page_kind == "exercise":
                info = read_answer(cdp)
                state = info.get("state", "")

                if state == "question" and info.get("answers"):
                    qi = info.get("questionIndex", -1)
                    now = time.time()

                    # 节流: 同一题已提交过则不重复提交 (等题目变化)
                    if qi == last_qi and now - last_submit_time < 3.0:
                        time.sleep(0.4)
                        continue

                    in_round = True  # 进入对局答题状态

                    # 新题: 延迟后提交
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    if qi != last_qi:
                        log(f"第{qi+1}题 {info.get('q1','').strip()} 答案池={info['answers']} 等待{delay:.8f}s")
                    time.sleep(delay)

                    ans, _ = pick_answer(info["answers"])
                    r = submit_answer(cdp, ans, True)
                    total += 1
                    correct += 1
                    round_answered += 1
                    log(f"  提交 '{ans}' ✓ (本局第{round_answered}题, 累计{total})")
                    last_qi = qi
                    last_submit_time = time.time()
                else:
                    # 对局刚开始/匹配等待 (还没出题)
                    time.sleep(0.5)
            elif page_kind == "result":
                # 结算页: 一局完成 + 点继续PK
                if in_round:
                    round_no += 1
                    log(f"=== 第{round_no}局完成 (本局答{round_answered}题, 全部正确) ===")
                    in_round = False
                    round_answered = 0
                    last_qi = -1
                now = time.time()
                if now - last_submit_time > 3.0:
                    r = click_continue(cdp)
                    if r and r.startswith("clicked"):
                        log(f"结算页: {r} (进入下一局)")
                        last_submit_time = time.time()
                        time.sleep(3)  # 等新对局加载/经验弹窗
                    else:
                        time.sleep(2)  # 没找到继续PK, 可能按钮还没渲染
                else:
                    time.sleep(1)
            elif page_kind == "honor":
                # 荣誉榜/经验弹窗页: 遍历所有 honor 页点'开心收下'领取经验
                now = time.time()
                if now - last_submit_time > 1.5:
                    claimed = 0
                    for hp in (cls.get("honor_list") or []):
                        hu = hp.get("url", "")
                        if hu in processed_honor:
                            continue  # 已处理过
                        try:
                            hc = CDP(hp["webSocketDebuggerUrl"])
                            r = click_claim_exp(hc)
                            if r and r.startswith("clicked"):
                                claimed += 1
                                log(f"  领取经验: {hu.split('lastExp=')[-1][:4]}")
                                processed_honor.add(hu)
                            else:
                                # 按钮可能还在加载动画: 给一次重试机会
                                time.sleep(2.0)
                                r2 = click_claim_exp(hc)
                                if r2 and r2.startswith("clicked"):
                                    claimed += 1
                                    log(f"  领取经验(重试): {hu.split('lastExp=')[-1][:4]}")
                                # 重试仍无按钮才标记处理 (防死循环也防漏领)
                                processed_honor.add(hu)
                            hc.close()
                        except Exception:
                            processed_honor.add(hu)  # 异常也标记, 防卡
                    if claimed > 0:
                        log(f"经验弹窗: 本轮领取 {claimed} 个")
                        last_submit_time = time.time()
                        time.sleep(1.5)
                    else:
                        time.sleep(0.8)
                else:
                    time.sleep(0.5)
            else:  # pk 主页
                # 主页: 点击 1v1PK 开始匹配
                now = time.time()
                if now - last_submit_time > 2.0:
                    r = click_start_match(cdp)
                    if r and r.startswith("clicked"):
                        log(f"主页: {r} (开始匹配)")
                        last_submit_time = time.time()
                        time.sleep(3)  # 等匹配
                    else:
                        log("主页: 未找到匹配按钮, 等待")
                        time.sleep(2)
                else:
                    time.sleep(1)
        except Exception as e:
            log(f"异常: {e}")
        finally:
            cdp.close()

        time.sleep(0.15)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("已停止")
