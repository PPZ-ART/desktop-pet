"""智能体监控：本机 ZCode / WorkBuddy 的 token 用量、额度窗口、调用智能体

数据来源：
- ZCode   ~/.zcode/cli/db/db.sqlite 的 model_usage 表（按智能体/模型聚合）
- WorkBuddy ~/.workbuddy/workbuddy.db 的 sessions + session_usage 表
- 套餐剩余额度无公开 API（凭证加密存储），用官方口径的 5 小时 / 7 天滚动窗口
  已用量呈现，精确剩余以 https://z.ai/manage-apikey/billing 为准

调用智能体：ZCode CLI 的无头模式（-p）不加载已保存的模型选择（0.17.0 实测
-p / -c / --resume 都报 "Select a model before sending a message"），
所以派发 = 任务写进剪贴板 + 打开 ZCode 桌面端，粘贴发送即可。
"""
import os
import json
import time
import uuid
import base64
import socket
import sqlite3
import datetime
import hmac
import hashlib
import urllib.request
import urllib.parse

基目录 = os.path.dirname(os.path.abspath(__file__))

# 智能体路径不写死：环境变量 → 桌面/开始菜单快捷方式 → 常见安装目录
# 想手动指定就设 ZCODE_PATH / WORKBUDDY_PATH
ZCODE_DB = os.path.join(os.path.expanduser("~"), ".zcode", "cli", "db", "db.sqlite")
WORKBUDDY_DB = os.path.join(os.path.expanduser("~"), ".workbuddy", "workbuddy.db")
额度页面 = "https://z.ai/manage-apikey/billing"
快捷方式目录们 = [
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                 r"Microsoft\Windows\Start Menu\Programs"),
]
_快捷方式缓存 = None


def 扫快捷方式(重新=True):
    """{快捷方式名: exe 路径}，扫桌面 + 开始菜单（含子目录），结果缓存"""
    global _快捷方式缓存
    if _快捷方式缓存 is not None and not 重新:
        return _快捷方式缓存
    表 = {}
    try:
        import glob
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        for 目录 in 快捷方式目录们:
            if not 目录 or not os.path.isdir(目录):
                continue
            for lnk in glob.glob(os.path.join(目录, "**", "*.lnk"), recursive=True):
                名 = os.path.splitext(os.path.basename(lnk))[0]
                if 名 in 表:
                    continue
                try:
                    目标 = shell.CreateShortCut(lnk).Targetpath
                except Exception:
                    目标 = ""
                if 目标 and 目标.lower().endswith(".exe") and os.path.exists(目标):
                    表[名] = 目标
                elif not 目标:
                    表[名] = lnk  # Store/UWP 应用没有 exe 路径，直接开快捷方式
    except Exception:
        pass
    _快捷方式缓存 = 表
    return 表


排除词 = ("卸载", "uninstall", "help", "帮助", "readme", "说明", "更新", "update")


def _是目标(名):
    """排除卸载/帮助/说明类快捷方式"""
    低 = 名.lower()
    return not any(k in 低 for k in 排除词)


def 找应用(*关键词, 环境变量=""):
    """按关键词找本机应用 exe：环境变量优先，其次桌面/开始菜单快捷方式名匹配"""
    if 环境变量:
        指定 = os.environ.get(环境变量, "").strip().strip('"')
        if 指定 and os.path.exists(指定):
            return 指定
    for 名, 路径 in 扫快捷方式(重新=False).items():
        低 = 名.lower()
        if any(k in 低 for k in 关键词) and _是目标(名):
            return 路径
    return ""


def zcode路径():
    return 找应用("zcode", "智谱", 环境变量="ZCODE_PATH")


def workbuddy路径():
    return 找应用("workbuddy", "buddy", 环境变量="WORKBUDDY_PATH")


def _只读连接(路径):
    if not os.path.exists(路径):
        return None
    try:
        uri = "file:" + 路径.replace("\\", "/") + "?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=2)
    except Exception:
        return None


def 万(n):
    """token 数转可读文本：256.4万 / 8.5千 / 320"""
    n = int(n)
    if n >= 10000:
        return ("%.1f万" % (n / 10000)).replace(".0万", "万")
    if n >= 1000:
        return "%.1f千" % (n / 1000)
    return str(n)


# ===== ZCode 用量（直读本地数据库，含智能体维度）=====
def zcode用量():
    """返回 {"总token", "会话数", "模型": [...], "智能体": [...], "窗口5小时", "窗口7天"}，读不到返回 None"""
    con = _只读连接(ZCODE_DB)
    if con is None:
        return None
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_usage'")
        if cur.fetchone() is None:
            return None
        结果 = {"名称": "ZCode", "模型": [], "智能体": []}
        cur.execute("""SELECT COALESCE(SUM(provider_total_tokens),0),
                              COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0),
                              COUNT(*), COUNT(DISTINCT session_id)
                       FROM model_usage WHERE status='completed'""")
        总计, 输入, 输出, 请求数, 会话数 = cur.fetchone()
        结果.update(总token=总计, 输入=输入, 输出=输出, 请求=请求数, 会话数=会话数)
        cur.execute("""SELECT model_id, COUNT(*), COALESCE(SUM(provider_total_tokens),0)
                       FROM model_usage WHERE status='completed'
                       GROUP BY model_id ORDER BY 3 DESC""")
        结果["模型"] = [{"模型": r[0] or "?", "请求": r[1], "总token": r[2]} for r in cur.fetchall()]
        cur.execute("""SELECT COALESCE(agent,'(未知)'), COUNT(*), COALESCE(SUM(provider_total_tokens),0)
                       FROM model_usage WHERE status='completed'
                       GROUP BY 1 ORDER BY 3 DESC""")
        结果["智能体"] = [{"名称": r[0], "请求": r[1], "总token": r[2]} for r in cur.fetchall()]
        结果.update(_窗口用量(cur))
        return 结果
    except Exception:
        return None
    finally:
        con.close()


def _窗口用量(cur):
    """套餐官方口径的两个滚动窗口已用量（5 小时窗口 + 7 天窗口）"""
    现在 = time.time() * 1000
    out = {}
    for 名, 秒 in (("窗口5小时", 5 * 3600), ("窗口7天", 7 * 86400)):
        cur.execute("SELECT COALESCE(SUM(provider_total_tokens),0) FROM model_usage WHERE started_at >= ?",
                    (现在 - 秒 * 1000,))
        out[名] = cur.fetchone()[0]
    return out


# ===== WorkBuddy 用量 =====
def workbuddy用量():
    """返回 {"会话数", "上下文占用", "积分", "会话": [...]}，读不到返回 None。
    注意：used 是各会话当前上下文占用量（不是累计消耗）；积分是本地记录的累计消耗，
    账户真实余额在云端，本地库没有，只能给控制台链接。"""
    con = _只读连接(WORKBUDDY_DB)
    if con is None:
        return None
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_usage'")
        if cur.fetchone() is None:
            return None
        结果 = {"名称": "WorkBuddy", "会话": []}
        cur.execute("""SELECT COUNT(*), COALESCE(SUM(u.used),0), COALESCE(SUM(u.size),0)
                       FROM session_usage u""")
        会话数, 上下文, 窗口总 = cur.fetchone()
        结果["会话数"] = 会话数
        结果["上下文占用"] = 上下文
        结果["窗口总"] = 窗口总
        结果["总token"] = 上下文  # 兼容旧字段名
        积分 = 0.0
        请求数 = 0
        去重 = {}
        cur.execute("SELECT credit_json FROM session_usage WHERE credit_json IS NOT NULL")
        for (cj,) in cur.fetchall():
            try:
                条目 = json.loads(cj)
            except Exception:
                continue
            for k, v in 条目.items():  # 按请求 id 去重，避免同一请求重复累加
                try:
                    去重[k] = float(v)
                except Exception:
                    pass
        积分 = sum(去重.values())
        请求数 = len(去重)
        结果["积分"] = round(积分, 1)
        结果["积分请求数"] = 请求数
        cur.execute("""SELECT COALESCE(NULLIF(s.custom_title,''), s.title, '未命名'),
                              s.model, u.used, u.size
                       FROM session_usage u JOIN sessions s ON s.id = u.session_id
                       ORDER BY u.updated_at DESC LIMIT 8""")
        for 标题, 模型, 已用, 窗口 in cur.fetchall():
            结果["会话"].append({"标题": 标题, "模型": 模型 or "?",
                                 "已用": 已用 or 0, "窗口": 窗口 or 0})
        return 结果
    except Exception:
        return None
    finally:
        con.close()


# ===== 文本输出 =====
def 汇总文本():
    """短汇总，给气泡和语音播报（一两句话）"""
    try:
        z = zcode用量()
        w = workbuddy用量()
    except Exception as e:
        return "智能体用量读取失败：" + str(e)
    段 = []
    if z:
        段.append("ZCode 已用 %s token，最近 5 小时窗口 %s" % (万(z["总token"]), 万(z["窗口5小时"])))
    if w:
        段.append("WorkBuddy %d 个会话，上下文占用 %s" % (w["会话数"], 万(w["总token"])))
    if not 段:
        return "本机没找到 ZCode 或 WorkBuddy 的用量数据"
    k = 读密钥()
    deep = [x for x in k.get("DeepSeek", []) if x.strip()]
    if deep:
        try:
            d = deepseek余额(deep[0])
            if d and "失败" not in d:
                段.append(d.replace("（可用）", "").replace("（已停用）", ""))
        except Exception:
            pass
    return "；".join(段) + "。详细看智能体面板"


def 明细文本():
    """面板用的完整明细：WorkBuddy 在最前，ZCode 放最后"""
    行 = ["更新 %s" % time.strftime("%H:%M:%S")]
    try:
        w = workbuddy用量()
    except Exception as e:
        w = None
        行.append("WorkBuddy 数据读取失败: %s" % e)
    if w:
        行.append("【WorkBuddy】%d 个会话 | 上下文占用 %s | 已用积分 %s（%d 次请求）" %
                  (w["会话数"], 万(w["总token"]), w["积分"], w.get("积分请求数", 0)))
        行.append("  余额在云端，本地库只记消耗；真实余额看 workbuddy.cn 账户页")
        if w["会话"]:
            行.append("  最近会话（已用/上下文窗口）:")
            for s in w["会话"]:
                剩 = ""
                if s["窗口"]:
                    剩 = "  剩 %d%%" % max(0, round((s["窗口"] - s["已用"]) / s["窗口"] * 100))
                行.append("    %-24s %8s/%s%s" % (s["标题"][:24], 万(s["已用"]), 万(s["窗口"]), 剩))
        行.append("")
    try:
        z = zcode用量()
    except Exception as e:
        z = None
        行.append("ZCode 数据读取失败: %s" % e)
    if z:
        行.append("【ZCode】共 %s token | %d 次请求 | %d 个会话" %
                  (万(z["总token"]), z["请求"], z["会话数"]))
        if z["模型"]:
            行.append("  模型:")
            for m in z["模型"]:
                行.append("    %-18s %10s  (%d 次请求)" % (m["模型"], 万(m["总token"]), m["请求"]))
        if z["智能体"]:
            行.append("  智能体:")
            for a in z["智能体"]:
                行.append("    %-18s %10s  (%d 次请求)" % (a["名称"], 万(a["总token"]), a["请求"]))
        行.append("  额度窗口: 最近5小时 %s | 最近7天 %s" % (万(z["窗口5小时"]), 万(z["窗口7天"])))
        行.append("")
    行.append("【剩余额度】套餐按 5 小时窗口 + 每周窗口双重限流（非峰值时段按半价计）。")
    行.append("  上方两个窗口数值即当前周期已用量，精确剩余与上限以官网为准。")
    return "\n".join(行)


_上次用量快照 = {"token": None}


def 活动提示():
    """WorkBuddy token 比上次多 → 说明刚干完活，返回提示文本；否则空串"""
    w = workbuddy用量()
    if not w:
        return ""
    现 = w["总token"]
    旧 = _上次用量快照["token"]
    _上次用量快照["token"] = 现
    if 旧 is None or 现 <= 旧:
        return ""
    return "WorkBuddy 刚用了 %s token，上下文占用 %s｜已用积分 %s" % (
        万(现 - 旧), 万(现), w["积分"])


def 汇总一行(数据源="全部"):
    """挂件用：按数据源返回一句话。数据源 = 全部 / WorkBuddy / ZCode / DeepSeek"""
    片 = []
    if 数据源 in ("全部", "WorkBuddy"):
        w = workbuddy用量()
        if w:
            片.append("WB 上下文 %s｜积分 %s" % (万(w["总token"]), w["积分"]))
    if 数据源 in ("全部", "ZCode"):
        z = zcode用量()
        if z:
            片.append("ZCode %s token" % 万(z["总token"]))
    if 数据源 in ("全部", "DeepSeek"):
        k = [x for x in 读密钥().get("DeepSeek", []) if str(x).strip()]
        if k:
            try:
                行 = deepseek余额(k[0], "DeepSeek")
                if 行 and "失败" not in 行:
                    片.append(行.replace("DeepSeek  ", "").replace("（可用）", ""))
            except Exception:
                pass
    return " ｜ ".join(片) if 片 else "未读到数据"


# ===== 调用智能体 =====
def _复制到剪贴板(文本):
    """win32 剪贴板写入（CF_UNICODETEXT），不依赖 tkinter"""
    import ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x2000
    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    u32.OpenClipboard.restype = ctypes.c_bool
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    缓冲 = ctypes.create_unicode_buffer(文本)
    字节 = (len(缓冲) + 1) * 2
    for 尝试 in range(6):  # 剪贴板可能被别的程序短暂占用，重试
        if not u32.OpenClipboard(None):
            time.sleep(0.15)
            continue
        try:
            u32.EmptyClipboard()
            句柄 = k32.GlobalAlloc(GMEM_MOVEABLE, 字节)
            指针 = k32.GlobalLock(句柄)
            ctypes.memmove(指针, 缓冲, 字节)
            k32.GlobalUnlock(句柄)
            if u32.SetClipboardData(CF_UNICODETEXT, 句柄):
                return True
        except Exception:
            pass
        finally:
            u32.CloseClipboard()
        time.sleep(0.15)
    return False


def 调用智能体(任务, 目标="WorkBuddy", 自动发送=True, 模式="新窗口"):
    """派发任务：复制进剪贴板 → 打开目标应用 → 等窗口出现 → 置前 →
    （新窗口时 Ctrl+N）→ Ctrl+V 粘贴 → Enter 发送。
    返回 (成功bool, 给用户的文案)。全程写 agent_task.log 备查。"""
    剪贴板OK = _复制到剪贴板(任务)
    if not 剪贴板OK:
        return False, "剪贴板写入失败，无法派发"
    目标们 = dict(智能体目标列表() or 刷新目标缓存())
    路径 = 目标们.get(目标)
    if not 路径:
        return False, "没找到智能体「%s」，桌面或开始菜单里得有它的快捷方式" % 目标
    try:
        os.startfile(路径)
    except Exception as e:
        return False, "打开 %s 失败: %s" % (目标, str(e)[:60])
    if not 自动发送:
        return True, "已复制并打开 %s，粘贴发送即可" % 目标
    发送OK = _自动粘贴发送(路径, 新窗口=(模式 == "新窗口"))
    if 发送OK:
        _派发日志("%s 已直发任务（%s）: %s" % (目标, 模式, 任务[:60]))
        return True, "任务已直接发送给 %s（%s）" % (目标, 模式)
    _派发日志("%s 直发失败(窗口/焦点)，任务留在剪贴板: %s" % (目标, 任务[:60]))
    return True, "%s 已打开，但没能自动输入——任务在剪贴板里，粘贴发送即可" % 目标


def _派发日志(内容):
    try:
        with open(os.path.join(基目录, "agent_task.log"), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%m-%d %H:%M:%S"), 内容))
    except Exception:
        pass


def _进程名(pid):
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    k32.OpenProcess.restype = ctypes.c_void_p  # 64 位句柄，默认 c_int 会被截断
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        大小 = ctypes.c_uint32(512)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(大小)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k32.CloseHandle(h)


def _按键组合(ctrl, vk):
    import ctypes
    u32 = ctypes.windll.user32
    KEYUP = 0x0002
    if ctrl:
        u32.keybd_event(0x11, 0, 0, 0)      # Ctrl 按下
    u32.keybd_event(vk, 0, 0, 0)
    u32.keybd_event(vk, 0, KEYUP, 0)
    if ctrl:
        u32.keybd_event(0x11, 0, KEYUP, 0)


def _自动粘贴发送(目标路径, 最长等=30, 新窗口=True):
    """等目标应用的窗口出现 → 置前并确认焦点 →（新窗口时 Ctrl+N）→ Ctrl+V / Enter。
    焦点确认失败就不发键，防止打错地方。"""
    import win32gui
    import win32process
    if 目标路径.lower().endswith(".lnk"):
        _派发日志("Store 应用 %s 无法按进程名定位窗口，任务留在剪贴板" % os.path.basename(目标路径))
        return False
    exe名 = os.path.basename(目标路径).lower()

    def 找窗口():
        找到 = []

        def 回调(句柄, _):
            try:
                if not win32gui.IsWindowVisible(句柄):
                    return
                if not win32gui.GetWindowText(句柄):
                    return
                _, pid = win32process.GetWindowThreadProcessId(句柄)
                if _进程名(pid) == exe名:
                    找到.append(句柄)
            except Exception:
                pass

        win32gui.EnumWindows(回调, None)
        return 找到[0] if 找到 else None

    截止 = time.time() + 最长等
    while time.time() < 截止:
        窗 = 找窗口()
        if 窗:
            try:
                win32gui.ShowWindow(窗, 9)  # SW_RESTORE
            except Exception:
                pass
            for _ in range(3):
                try:
                    win32gui.SetForegroundWindow(窗)
                except Exception:
                    pass
                time.sleep(0.4)
                if win32gui.GetForegroundWindow() == 窗:
                    break
            if win32gui.GetForegroundWindow() != 窗:
                return False  # 焦点没拿到，宁可不发键
            if 新窗口:
                _按键组合(True, 0x4E)   # Ctrl+N 新对话（不支持的程序无副作用）
                time.sleep(0.6)
            _按键组合(True, 0x56)   # Ctrl+V
            time.sleep(0.6)
            _按键组合(False, 0x0D)  # Enter 发送
            return True
        time.sleep(0.8)
    return False


# 本机可能装了多个智能体（桌面快捷方式里按关键词识别）
桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
目标关键词 = ("workbuddy", "buddy", "zcode", "codex", "deepseek", "agent",
             "豆包", "doubao", "kimi", "通义", "元宝", "千问", "qwen",
             "chatgpt", "gpt", "openai", "claude", "gemini", "copilot",
             "perplexity", "grok", "poe", "trae", "cursor", "windsurf", "cherry")
目标优先 = {"workbuddy": 0, "zcode": 99}  # WorkBuddy 第一，ZCode 最后
_目标缓存 = []

# 用户手动「检索本地智能体」后添加的目标与自定义平台，存这里
额外文件 = os.path.join(基目录, "agent_extra.json")


def 读额外():
    """{"目标": [{"名称":,"路径":}], "平台": {"名称": ["key"]}}"""
    try:
        d = json.load(open(额外文件, encoding="utf-8"))
    except Exception:
        return {"目标": [], "平台": {}}
    d.setdefault("目标", [])
    d.setdefault("平台", {})
    return d


def 存额外(数据):
    json.dump(数据, open(额外文件, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def 候选智能体():
    """扫描本机候选（桌面+开始菜单里像 AI 的软件），供「检索本地智能体」勾选"""
    额外 = {x["名称"] for x in 读额外()["目标"]}
    已有 = {n for n, _ in 智能体目标列表()}
    候选 = []
    for 名, 路径 in 扫快捷方式().items():
        低 = 名.lower()
        if not _是目标(名) or 名 in 额外 or 名 in 已有:
            continue
        if any(kw in 低 for kw in 目标关键词):
            候选.append({"名称": 名, "路径": 路径})
    return 候选


def 智能体目标列表():
    """[(名称, 启动路径...)]；启动时后台建缓存，这里只读缓存"""
    return list(_目标缓存)


def 刷新目标缓存():
    """识别本机智能体，写缓存（放后台线程调用）"""
    global _目标缓存
    目标 = []
    找 = zcode路径()
    if 找:
        目标.append(("ZCode", 找))
    找 = workbuddy路径()
    if 找:
        目标.append(("WorkBuddy", 找))
    已有 = {n.lower() for n, _ in 目标}
    for 名, 路径 in 扫快捷方式().items():
        低 = 名.lower()
        if 低 in 已有 or not _是目标(名) or not any(kw in 低 for kw in 目标关键词):
            continue
        目标.append((名, 路径))
        已有.add(低)
    for 项 in 读额外()["目标"]:  # 用户手动添加的排最前（优先级 0.5）
        名, 路径 = 项.get("名称", ""), 项.get("路径", "")
        if 名 and 路径 and os.path.exists(路径) and 名.lower() not in 已有:
            目标.append((名, 路径))
            已有.add(名.lower())
    目标.sort(key=lambda x: 目标优先.get(x[0].lower(), 50))
    _目标缓存 = 目标
    return 目标


def 打开智能体应用(哪个="WorkBuddy"):
    """按名称启动本机智能体应用，返回 True/False（缓存空时先现扫一次）"""
    名单 = 智能体目标列表() or 刷新目标缓存()
    for 名称, 路径 in 名单:
        if 名称.lower() == 哪个.lower():
            try:
                os.startfile(路径)
                return True
            except Exception:
                return False
    return False


def 打开平台页面():
    """打开所有已配置平台的官方额度/用量页，返回打开清单文本"""
    页 = 平台页面列表()
    for _, url in 页:
        try:
            os.startfile(url)
        except Exception:
            pass
    return "、".join(名 for 名, _ in 页)


def 平台页面列表():
    """[(名称, 控制台地址)]：已配置密钥的平台对应的官方额度/用量页"""
    k = 读密钥()
    页 = [("ZCode(Z.ai) 额度", 额度页面),
         ("WorkBuddy 账户", "https://www.workbuddy.cn")]  # 本地无余额接口，跳官网看
    if any(x.strip() for x in k.get("DeepSeek", [])):
        页.append(("DeepSeek 用量", "https://platform.deepseek.com/usage"))
    if any(x.strip() for x in k.get("智谱", [])):
        页.append(("智谱 财务", "https://open.bigmodel.cn/finance-center/finance/overview"))
    if any(x.strip() for x in k.get("阿里云", [])):
        页.append(("阿里云 卡券余额", 阿里云卡券页))
        页.append(("阿里云 费用", "https://usercenter2.aliyun.com/finance/expense-report"))
    if any(x.strip() for x in k.get("高德", [])):
        页.append(("高德 用量管理", 高德流量页))
    return 页


def 打开额度页面():
    try:
        os.startfile(额度页面)
        return True
    except Exception:
        return False


# ===== 平台余额（各平台官方接口，密钥来自 agent_keys.json）=====
密钥文件 = os.path.join(基目录, "agent_keys.json")
高德控制台 = "https://console.amap.com/dev/key/app"
高德流量页 = "https://console.amap.com/dev/flow/manage"
阿里云卡券页 = "https://billing-cost.console.aliyun.com/coupons/coupon"


内置平台 = ("DeepSeek", "智谱", "阿里云", "高德")


def 读密钥():
    """{平台名: [密钥行...]}，含自定义平台；兼容旧版单字符串值和旧的阿里云分字段"""
    try:
        原始 = json.load(open(密钥文件, encoding="utf-8"))
    except Exception:
        原始 = {}
    结果 = {k: ([v] if isinstance(v, str) else v) for k, v in 原始.items()}
    旧ID = 结果.pop("阿里云ID", [])
    旧Secret = 结果.pop("阿里云Secret", [])
    if "阿里云" not in 结果 and 旧ID and 旧Secret and 旧ID[0].strip() and 旧Secret[0].strip():
        结果["阿里云"] = ["%s,%s" % (旧ID[0].strip(), 旧Secret[0].strip())]
    for 名, 值 in 读额外()["平台"].items():  # 自定义平台
        if 名 not in 内置平台:
            结果.setdefault(名, [值] if isinstance(值, str) else 值)
    return 结果


def 存密钥(映射):
    归一 = {k: ([v] if isinstance(v, str) else v) for k, v in 映射.items()}
    内置 = {k: v for k, v in 归一.items() if k in 内置平台}
    自定义 = {k: v for k, v in 归一.items() if k not in 内置平台}
    json.dump(内置, open(密钥文件, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    额外 = 读额外()
    额外["平台"] = 自定义
    存额外(额外)


def _短错(e):
    """HTTP 错误尽量带出响应体里的原因"""
    if hasattr(e, "read"):
        try:
            return e.read().decode("utf-8", "ignore")[:120]
        except Exception:
            pass
    return str(e)[:120]


_代理端口们 = (7890, 7897, 10809, 10808, 1080, 8080, 8888)


def _本机代理():
    """探测常见本地代理端口（Clash/V2Ray 等），返回 http://127.0.0.1:端口 或空串"""
    指定 = os.environ.get("PET_PROXY", "").strip()
    if 指定:
        return 指定
    for 端口 in _代理端口们:
        try:
            socket.create_connection(("127.0.0.1", 端口), timeout=0.3).close()
            return "http://127.0.0.1:%d" % 端口
        except Exception:
            continue
    return ""


def _get_json(url, 头=None, 超时=12):
    """先直连（走系统/环境代理），失败再试本机代理端口"""
    req = urllib.request.Request(url, headers=头 or {})
    try:
        with urllib.request.urlopen(req, timeout=超时) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as 首错:
        代理 = _本机代理()
        if not 代理:
            raise 首错
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": 代理, "https": 代理}))
        with opener.open(req, timeout=超时) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))


def deepseek余额(key, 标签="DeepSeek"):
    if not key:
        return None
    try:
        d = _get_json("https://api.deepseek.com/user/balance",
                      {"Authorization": "Bearer " + key.strip()})
        信息 = (d.get("balance_infos") or [{}])[0]
        状态 = "可用" if d.get("is_available") else "已停用"
        return "%s  余额 ¥%s（%s）" % (标签, 信息.get("total_balance", "?"), 状态)
    except Exception as e:
        return "%s  查询失败: %s" % (标签, _短错(e))


def 智谱余额(key, 标签="智谱"):
    """官方无平台余额接口；编码计划额度走 /api/monitor/usage/quota/limit"""
    if not key:
        return None
    控制台 = "open.bigmodel.cn/finance-center/finance/overview"
    try:
        d = _get_json("https://open.bigmodel.cn/api/monitor/usage/quota/limit",
                      {"Authorization": "Bearer " + key.strip()})
    except Exception as e:
        return "%s  查询失败: %s" % (标签, _短错(e))
    if d.get("code") not in (200, 0, None):
        消 = str(d.get("msg", d))[:80]
        if "coding plan" in 消:
            return "%s  key 未绑定编码计划；平台余额无公开接口，控制台: %s" % (标签, 控制台)
        return "%s  查询失败: %s" % (标签, 消)
    数据 = d.get("data") or {}
    片 = []

    def 走(o, 前缀=""):
        if isinstance(o, dict):
            for kk, vv in o.items():
                走(vv, 前缀 + "." + kk if 前缀 else kk)
        elif isinstance(o, (int, float, str, bool)) and 前缀:
            片.append("%s=%s" % (前缀, o))

    走(数据)
    if not 片:
        return "%s  编码计划额度: %s" % (标签, str(数据)[:100])
    return "%s  编码计划额度: %s" % (标签, "，".join(片[:6]))


def 高德行(key, 标签="高德"):
    """高德无余额 API，用量在控制台「用量管理」看；这里只做登记与跳转"""
    if not key:
        return None
    return "%s  已登记；高德用量看 %s" % (标签, 高德流量页)


def _阿里云签名请求(参数, key_id, secret):
    """BSS OpenAPI RPC 签名（HMAC-SHA1，仅用标准库）"""
    基础 = {"Format": "JSON", "Version": "2017-12-14", "AccessKeyId": key_id,
           "SignatureMethod": "HMAC-SHA1", "SignatureVersion": "1.0",
           "SignatureNonce": str(uuid.uuid4()),
           "Timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    基础.update(参数)
    编码 = lambda s: urllib.parse.quote(str(s), safe="-_.~")
    查询串 = "&".join("%s=%s" % (编码(k), 编码(基础[k])) for k in sorted(基础))
    待签 = "GET&" + 编码("/") + "&" + 编码(查询串)
    签名 = base64.b64encode(hmac.new((secret + "&").encode(),
                                     待签.encode(), hashlib.sha1).digest()).decode()
    return _get_json("https://business.aliyuncs.com/?%s&Signature=%s"
                     % (查询串, urllib.parse.quote(签名, safe="")))


def _找余额(对象):
    """在返回 JSON 里就地找金额字段（不同接口结构有差异）"""
    if isinstance(对象, dict):
        for k in ("AvailableAmount", "Balance", "total_balance"):
            if k in 对象:
                return 对象[k]
        for v in 对象.values():
            r = _找余额(v)
            if r is not None:
                return r
    elif isinstance(对象, list):
        for v in 对象:
            r = _找余额(v)
            if r is not None:
                return r
    return None


def _找券额度(o, 累计):
    """递归找所有带 Balance 字段的条目（卡券结构随版本变化，只认字段）"""
    if isinstance(o, dict):
        if "Balance" in o:
            try:
                累计.append(float(o["Balance"]))
            except Exception:
                pass
        for v in o.values():
            _找券额度(v, 累计)
    elif isinstance(o, list):
        for v in o:
            _找券额度(v, 累计)


def _找字段值(o, 名, 累计):
    """递归收集 JSON 里指定字段的可解析数值"""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == 名:
                try:
                    累计.append(float(v))
                except Exception:
                    pass
            _找字段值(v, 名, 累计)
    elif isinstance(o, list):
        for v in o:
            _找字段值(v, 名, 累计)


def 阿里云余额(key_id, secret, 标签="阿里云/百炼"):
    if not key_id or not secret:
        return None
    try:
        d = _阿里云签名请求({"Action": "QueryAccountBalance"}, key_id, secret)
        现金 = _找余额(d)
        附加 = ""
        try:
            c = _阿里云签名请求({"Action": "QueryCashCoupons"}, key_id, secret)
            额度们 = []
            _找券额度(c, 额度们)
            总额 = sum(额度们)
            if 总额:
                附加 += "，卡券 ¥%.2f" % 总额
        except Exception:
            pass
        try:
            # 百炼的 token 资源包也在费用中心，TotalAmount = 资源包总剩余
            r = _阿里云签名请求({"Action": "QueryResourcePackageList",
                                 "PageSize": "20", "PageNum": "1"}, key_id, secret)
            vals = []
            _找字段值(r, "TotalAmount", vals)
            if vals and max(vals):
                附加 += "，资源包剩余 ¥%.2f" % max(vals)
        except Exception:
            pass
        return "%s  余额 ¥%s%s" % (标签, 现金 if 现金 is not None else "?", 附加)
    except Exception as e:
        return "%s  查询失败: %s（卡券余额看 %s）" % (标签, _短错(e), 阿里云卡券页)


def 平台余额文本():
    """逐平台逐密钥查询余额（网络请求，放后台线程调用）"""
    k = 读密钥()
    行 = []
    for i, key in enumerate([x for x in k.get("DeepSeek", []) if x.strip()], 1):
        行.append(deepseek余额(key, "DeepSeek#%d" % i))
    for i, key in enumerate([x for x in k.get("智谱", []) if x.strip()], 1):
        行.append(智谱余额(key, "智谱#%d" % i))
    for i, 对 in enumerate([x for x in k.get("阿里云", []) if x.strip()], 1):
        if 对.startswith("sk-"):
            行.append("百炼#%d  sk- key 官方限制只能调模型，查额度用 AccessKey，控制台: bailian.console.aliyun.com" % i)
        elif "," in 对:
            key_id, secret = 对.split(",", 1)
            if key_id.strip() and secret.strip():
                行.append(阿里云余额(key_id.strip(), secret.strip(), "百炼/阿里云#%d" % i))
            else:
                行.append("百炼#%d  AccessKeyID 或 Secret 为空" % i)
        else:
            行.append("百炼#%d  格式：AccessKeyID,AccessKeySecret（查余额/卡券/资源包）；sk- key 仅登记" % i)
    for i, key in enumerate([x for x in k.get("高德", []) if x.strip()], 1):
        行.append(高德行(key, "高德#%d" % i))
    for 名, 值们 in k.items():  # 自定义平台：只登记，不查询
        if 名 in 内置平台:
            continue
        有效 = [x for x in 值们 if x.strip()]
        if 有效:
            行.append("%s  已登记 %d 个密钥（自定义平台，无内置余额查询）" % (名, len(有效)))
    行 = [x for x in 行 if x]
    if not 行:
        return "【平台余额】未配置密钥 —— 右键菜单「配置智能体」填入后可查"
    return "【平台余额】\n" + "\n".join(行)
