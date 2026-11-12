import os
import sys

# PyInstaller 冻结环境：必须在任何 import torch/funasr 之前修好 DLL 加载
if getattr(sys, "frozen", False):
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # OpenMP 冲突（torch 与 onnxruntime）
    _系统 = os.path.join(os.environ.get("SystemRoot", r"C:/Windows"), "System32")
    # 关键：打包目录里的 msvcp140/vcruntime140 是旧版，会被 c10.dll 优先加载 → WinError 1114。
    # 先把系统运行库载入进程，同名 DLL 复用已加载版本，torch 才能初始化。
    try:
        import ctypes as _ct
        for _d in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_atomic_wait.dll",
                   "vcruntime140.dll", "vcruntime140_1.dll"):
            try:
                _ct.CDLL(os.path.join(_系统, _d))
            except Exception:
                pass
    except Exception:
        pass
    _根 = os.path.dirname(sys.executable)
    for _子 in ("_internal", os.path.join("_internal", "torch", "lib")):
        _p = os.path.join(_根, _子)
        if os.path.isdir(_p):
            try:
                os.add_dll_directory(_p)
            except Exception:
                pass

import math
import json
import random
import time
import difflib
import queue
import threading
import urllib.request
import tkinter as tk
from PIL import Image, ImageTk

基目录 = os.path.dirname(os.path.abspath(__file__))
帧目录 = os.path.join(基目录, "frames")
设置文件 = os.path.join(基目录, "settings.json")
状态文件 = os.path.join(基目录, "pet_state.json")
_密钥缓存 = {"值": None, "时间": 0.0}


def 取DeepSeek密钥():
    """环境变量 → agent_keys.json（配置窗口填的）→ settings.json，任一有值即用"""
    环境 = os.environ.get("DEEPSEEK_KEY", "").strip()
    if 环境:
        return 环境
    现在 = time.time()
    if _密钥缓存["值"] is not None and 现在 - _密钥缓存["时间"] < 10:
        return _密钥缓存["值"]
    值 = ""
    try:
        import agent_monitor
        for k in agent_monitor.读密钥().get("DeepSeek", []):
            if str(k).strip():
                值 = str(k).strip()
                break
    except Exception:
        pass
    if not 值:
        值 = str(设置.get("DeepSeek密钥", "")).strip()
    _密钥缓存.update(值=值, 时间=现在)
    return 值

# ===== 设置 =====
默认设置 = {"大小": 1.0, "速率": 7, "自由移动": False, "移动速度": 5, "语音唤醒": False,
            "睡眠模式": True, "点击音效": True, "自言自语": True, "余额挂件": False,
            "挂件数据源": "全部"}
设置 = dict(默认设置)
if os.path.exists(设置文件):
    try:
        设置.update(json.load(open(设置文件, encoding="utf-8")))
    except Exception:
        pass

# 旧版 settings.json 里「速率」存的是毫秒，换算成 0-10 档
if 设置["速率"] > 10:
    设置["速率"] = max(0, min(10, round((150 - 设置["速率"]) / 13)))

def 速率转毫秒(值):
    return int(150 - float(值) * 13)

def 保存设置():
    json.dump(设置, open(设置文件, "w", encoding="utf-8"))

# ===== 状态 =====
默认状态 = {"心情": 80, "饥饿": 80, "最后喂食": 0}
状态 = dict(默认状态)
if os.path.exists(状态文件):
    try:
        状态.update(json.load(open(状态文件, encoding="utf-8")))
    except Exception:
        pass

def 保存状态():
    json.dump(状态, open(状态文件, "w", encoding="utf-8"))

# ===== 窗口 =====
窗口 = tk.Tk()
窗口.overrideredirect(True)
窗口.attributes("-topmost", True)
窗口.attributes("-transparentcolor", "#010203")

# ===== 帧 =====
原始帧 = []
for 文件名 in sorted(os.listdir(帧目录)):
    if 文件名.endswith(".png"):
        原始帧.append(Image.open(os.path.join(帧目录, 文件名)).convert("RGBA"))
原宽, 原高 = 原始帧[0].size

def 生成帧(倍率):
    w, h = int(原宽 * 倍率), int(原高 * 倍率)
    return [ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS)) for img in 原始帧]

帧列表 = 生成帧(设置["大小"])
帧间隔 = 速率转毫秒(设置["速率"])
画布 = tk.Canvas(窗口, width=帧列表[0].width(), height=帧列表[0].height(),
                bg="#010203", highlightthickness=0)
画布.pack()
图片项 = 画布.create_image(0, 0, anchor="nw", image=帧列表[0])
当前帧 = 0
动画暂停 = False

def 播放():
    global 当前帧
    if not 动画暂停:
        当前帧 = (当前帧 + 1) % len(帧列表)
        画布.itemconfig(图片项, image=帧列表[当前帧])
    窗口.after(400 if 睡眠中() else 帧间隔, 播放)  # 夜里慢下来，像睡着


def 睡眠中():
    """23:00-7:00 且开了睡眠模式"""
    if not 设置.get("睡眠模式", True):
        return False
    时 = time.localtime().tm_hour
    return 时 >= 23 or 时 < 7

播放()

# ===== 线程安全消息队列（子线程结果回主线程）=====
消息队列 = queue.Queue()

def 轮询队列():
    try:
        while True:
            fn = 消息队列.get_nowait()
            fn()
    except queue.Empty:
        pass
    窗口.after(100, 轮询队列)

轮询队列()

# ===== 气泡 =====
气泡 = None

def 显示气泡(文字, 毫秒=4000):
    global 气泡
    if 气泡 is not None:
        try:
            气泡.destroy()
        except Exception:
            pass
    气泡 = tk.Toplevel(窗口)
    气泡.overrideredirect(True)
    气泡.attributes("-topmost", True)
    气泡.configure(bg="#010203")
    气泡.attributes("-transparentcolor", "#010203")  # 圆角外的角落透明

    测量 = tk.Label(气泡, text=文字, font=("Microsoft YaHei", 10), wraplength=240, justify="left")
    测量.update_idletasks()
    文字宽 = min(测量.winfo_reqwidth(), 240) + 2
    文字高 = 测量.winfo_reqheight()
    测量.destroy()

    内边 = 12
    宽 = 文字宽 + 内边 * 2
    高 = 文字高 + 内边 * 2
    画布 = tk.Canvas(气泡, width=宽, height=高, bg="#010203", highlightthickness=0)
    画布.pack()

    # Canvas 平滑多边形画圆角矩形
    r = 14
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    画布.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")
    画布.create_text(内边, 内边, text=文字, anchor="nw", fill="#ffffff",
                     font=("Microsoft YaHei", 10), width=240)

    屏宽 = 窗口.winfo_screenwidth()
    屏高 = 窗口.winfo_screenheight()
    宠左, 宠上 = 窗口.winfo_x(), 窗口.winfo_y()
    宠宽, 宠高 = 画布.winfo_width(), 画布.winfo_height()
    宠右, 宠下 = 宠左 + 宠宽, 宠上 + 宠高
    # 上方优先，其次下方，再左右，保证不压住宠物
    x = max(0, min(宠左 + (宠宽 - 宽) // 2, 屏宽 - 宽))
    if 宠上 >= 高 + 12:
        y = 宠上 - 高 - 10
    elif 屏高 - 宠下 >= 高 + 12:
        y = 宠下 + 10
    elif 屏宽 - 宠右 >= 宽 + 12:
        x, y = 宠右 + 10, 宠上 + (宠高 - 高) // 2
    else:
        x, y = max(0, 宠左 - 宽 - 10), 宠上 + (宠高 - 高) // 2
    气泡.geometry("+%d+%d" % (x, max(0, y)))
    气泡.after(毫秒, 气泡.destroy)

# ===== 拖动 / 抚摸 =====
def 按下(事件):
    global 动画暂停, 拖动中
    拖动中 = True
    窗口.偏移x = 事件.x_root - 窗口.winfo_x()
    窗口.偏移y = 事件.y_root - 窗口.winfo_y()
    窗口.按下x = 事件.x_root
    窗口.按下y = 事件.y_root
    动画暂停 = True

拖动轨迹 = []  # [(时间, x, y)]，用于松手时算惯性


def 拖动(事件):
    x = 事件.x_root - 窗口.偏移x
    y = 事件.y_root - 窗口.偏移y
    窗口.geometry("+%d+%d" % (x, y))
    拖动轨迹.append((time.time(), x, y))
    if len(拖动轨迹) > 6:
        del 拖动轨迹[0]


def 松开(事件):
    global 动画暂停, 拖动中
    动画暂停 = False
    位移 = abs(事件.x_root - 窗口.按下x) + abs(事件.y_root - 窗口.按下y)
    if 位移 < 5:
        拖动中 = False
        同步移动坐标()
        抚摸()  # 音效在抚摸里播，这里不要重复
        return
    甩出去()


惯性x = 惯性y = 0.0


def 甩出去():
    """松手带惯性滑行，停下后贴边"""
    global 拖动中, 惯性x, 惯性y
    if len(拖动轨迹) >= 2:
        段 = 拖动轨迹[-1][0] - 拖动轨迹[0][0]
        if 段 > 0.01:
            惯性x = (拖动轨迹[-1][1] - 拖动轨迹[0][1]) / 段 * 0.12
            惯性y = (拖动轨迹[-1][2] - 拖动轨迹[0][2]) / 段 * 0.12
    拖动轨迹.clear()
    惯性x = max(-60, min(60, 惯性x))  # 别甩太狠飞出屏幕
    惯性y = max(-60, min(60, 惯性y))
    拖动中 = True
    惯性步()


def 惯性步():
    global 惯性x, 惯性y, 拖动中
    if abs(惯性x) < 0.8 and abs(惯性y) < 0.8:
        惯性x = 惯性y = 0.0
        拖动中 = False
        贴边吸附()
        同步移动坐标()
        return
    屏宽, 屏高 = 窗口.winfo_screenwidth(), 窗口.winfo_screenheight()
    宠宽, 宠高 = 帧列表[0].width(), 帧列表[0].height()
    x = max(0, min(窗口.winfo_x() + int(惯性x), max(0, 屏宽 - 宠宽)))
    y = max(0, min(窗口.winfo_y() + int(惯性y), max(0, 屏高 - 宠高)))
    窗口.geometry("+%d+%d" % (x, y))
    惯性x *= 0.86
    惯性y *= 0.86
    窗口.after(16, 惯性步)


def 贴边吸附():
    """离屏幕边缘 28px 内就吸上去"""
    屏宽, 屏高 = 窗口.winfo_screenwidth(), 窗口.winfo_screenheight()
    宠宽, 宠高 = 帧列表[0].width(), 帧列表[0].height()
    x, y = 窗口.winfo_x(), 窗口.winfo_y()
    边距 = 28
    if x < 边距:
        x = 0
    elif x + 宠宽 > 屏宽 - 边距:
        x = 屏宽 - 宠宽
    if y < 边距:
        y = 0
    elif y + 宠高 > 屏高 - 边距:
        y = 屏高 - 宠高
    窗口.geometry("+%d+%d" % (max(0, x), max(0, y)))

画布.bind("<Button-1>", 按下)
画布.bind("<B1-Motion>", 拖动)
画布.bind("<ButtonRelease-1>", 松开)

# ===== 状态行为 =====
def 抚摸():
    状态["心情"] = min(100, 状态["心情"] + 5)
    保存状态()
    显示气泡("❤ 好舒服，心情 +5")
    播音效("摸")
    开心跳()


def 喂食():
    if time.time() - 状态["最后喂食"] < 5:
        显示气泡("刚吃过啦，歇会儿")
        return
    状态["饥饿"] = min(100, 状态["饥饿"] + 10)
    状态["最后喂食"] = time.time()
    保存状态()
    显示气泡("🍗 好吃，饥饿 +10")
    播音效("喂")
    开心跳()


def 开心跳(次=3):
    """原地蹦两下（结束回到原位，不干扰游走坐标）"""
    global 拖动中
    拖动中 = True
    try:
        基准x, 基准y = 窗口.winfo_x(), 窗口.winfo_y()
    except Exception:
        拖动中 = False
        return

    def 一步(i=0, 起跳=True):
        global 拖动中
        if i >= 次 * 2:
            窗口.geometry("+%d+%d" % (基准x, 基准y))
            同步移动坐标()
            拖动中 = False
            return
        窗口.geometry("+%d+%d" % (基准x, 基准y - (10 if 起跳 else 0)))
        窗口.after(85, lambda: 一步(i + 1, not 起跳))

    一步()

def 显示状态():
    显示气泡("心情 %d / 100\n饥饿 %d / 100" % (状态["心情"], 状态["饥饿"]))

def 衰减():
    状态["心情"] = max(0, 状态["心情"] - 1)
    状态["饥饿"] = max(0, 状态["饥饿"] - 2)
    保存状态()
    窗口.after(300000, 衰减)

窗口.after(300000, 衰减)

# ===== 提醒 =====
def 设提醒():
    输入窗 = tk.Toplevel(窗口)
    输入窗.overrideredirect(True)
    输入窗.attributes("-topmost", True)
    输入窗.configure(bg="#010203")
    输入窗.attributes("-transparentcolor", "#010203")

    宽, 高 = 260, 96
    c = tk.Canvas(输入窗, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 16
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    c.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")
    c.create_text(16, 13, text="几分钟后提醒？（回车确认）", anchor="nw",
                  fill="#cccccc", font=("Microsoft YaHei", 9))
    输入框 = tk.Entry(c, font=("Microsoft YaHei", 11), bg="#3a3a3a", fg="#ffffff",
                     insertbackground="#ffffff", relief="flat", justify="center")
    c.create_window(16, 40, window=输入框, anchor="nw", width=宽 - 32, height=26)
    输入框.focus_set()

    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 宽 // 2
    y = 窗口.winfo_y() - 高 - 10
    输入窗.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    def 提交(事件=None):
        try:
            分钟 = int(输入框.get().strip())
        except ValueError:
            分钟 = 0
        输入窗.destroy()
        if 分钟 > 0:
            窗口.after(分钟 * 60000, lambda: 显示气泡("⏰ 时间到！", 10000))

    输入框.bind("<Return>", 提交)
    输入框.bind("<Escape>", lambda e: 输入窗.destroy())

# ===== 设置（无级）=====
def 设大小(倍率):
    global 帧列表
    倍率 = round(float(倍率), 2)
    帧列表 = 生成帧(倍率)
    画布.config(width=帧列表[0].width(), height=帧列表[0].height())
    设置["大小"] = 倍率
    保存设置()

def 设速率(值):
    global 帧间隔
    值 = max(0, min(10, float(值)))
    帧间隔 = 速率转毫秒(值)
    设置["速率"] = 值
    保存设置()

# ===== 自由移动（无级随机游走）=====
移动当前x = 0.0
移动当前y = 0.0
移动角度 = random.uniform(0, math.pi * 2)
移动速度当前 = 1.5
游走中 = False
拖动中 = False
窗口矩形缓存 = []
矩形倒计时 = 0
阻挡计数 = 0
避让失效 = False  # 屏幕被窗口占满时放弃避让，保证宠物还能动

def 切换自由移动():
    设置["自由移动"] = not 设置["自由移动"]
    保存设置()
    if 设置["自由移动"]:
        显示气泡("自由移动：开")
        开始游走()
    else:
        游走中 = False
        显示气泡("自由移动：关")

def 开始游走():
    global 移动当前x, 移动当前y, 移动角度, 游走中
    移动当前x, 移动当前y = float(窗口.winfo_x()), float(窗口.winfo_y())
    移动角度 = random.uniform(0, math.pi * 2)
    游走中 = True
    窗口.after(30, 游走一步)

def 同步移动坐标():
    """拖动后同步内部坐标，避免松手瞬间跳回旧位置"""
    global 移动当前x, 移动当前y
    移动当前x, 移动当前y = float(窗口.winfo_x()), float(窗口.winfo_y())

def 游走一步():
    """无级随机游走：速度/方向连续小幅浮动，边界平滑折返，碰到窗口绕开"""
    global 移动当前x, 移动当前y, 移动角度, 移动速度当前, 矩形倒计时, 窗口矩形缓存
    global 阻挡计数, 避让失效
    if not 设置["自由移动"] or not 游走中 or 拖动中:
        if 设置["自由移动"] and 游走中:
            窗口.after(30, 游走一步)
        return
    屏宽 = 窗口.winfo_screenwidth()
    屏高 = 窗口.winfo_screenheight()
    宠宽, 宠高 = 帧列表[0].width(), 帧列表[0].height()
    基础 = max(0.4, float(设置.get("移动速度", 5)) * 0.3)

    # 无级随机：速度持续小幅浮动，方向持续轻微摆动（不整段匀速直线）
    移动速度当前 = max(基础 * 0.6, min(基础 * 1.5,
                                    移动速度当前 + random.uniform(-0.12, 0.12) * 基础))
    移动角度 += random.uniform(-0.18, 0.18)

    新x = 移动当前x + math.cos(移动角度) * 移动速度当前
    新y = 移动当前y + math.sin(移动角度) * 移动速度当前

    # 到边界平滑折返（不硬停、不回弹）
    边距 = 12
    if 新x < 边距 or 新x + 宠宽 > 屏宽 - 边距:
        移动角度 = math.pi - 移动角度
        移动速度当前 = 基础
    if 新y < 边距 or 新y + 宠高 > 屏高 - 边距:
        移动角度 = -移动角度
        移动速度当前 = 基础
    新x = max(边距, min(新x, max(边距, 屏宽 - 宠宽 - 边距)))
    新y = max(边距, min(新y, max(边距, 屏高 - 宠高 - 边距)))

    # 每 0.6 秒刷新一次其他窗口位置，命中就绕开（不进入已打开窗口）
    矩形倒计时 -= 1
    if 矩形倒计时 <= 0:
        矩形倒计时 = 20
        阻挡计数 = 0
        避让失效 = False  # 每 0.6 秒重新尝试避让
        try:
            窗口矩形缓存 = 获取窗口矩形()
        except Exception:
            窗口矩形缓存 = []
    已在窗口内 = 重叠(int(移动当前x), int(移动当前y), 宠宽, 宠高, 窗口矩形缓存)
    if (窗口矩形缓存 and not 避让失效 and not 已在窗口内
            and 重叠(int(新x), int(新y), 宠宽, 宠高, 窗口矩形缓存)):
        阻挡计数 += 1
        if 阻挡计数 > 8:
            避让失效 = True  # 四周全是窗口，躲不掉就照常走
        else:
            移动角度 += random.choice((-1, 1)) * random.uniform(1.2, 2.2)
            窗口.after(30, 游走一步)
            return
    elif 已在窗口内:
        阻挡计数 = 0

    移动当前x, 移动当前y = 新x, 新y
    窗口.geometry("+%d+%d" % (int(移动当前x), int(移动当前y)))
    窗口.after(30, 游走一步)

def 获取窗口矩形():
    """其他可见窗口的矩形（排除桌面/任务栏/宠物自身）"""
    import win32gui
    矩形列表 = []
    宠物宽, 宠物高 = 帧列表[0].width(), 帧列表[0].height()

    def 回调(句柄, _):
        try:
            if not win32gui.IsWindowVisible(句柄):
                return
            类名 = win32gui.GetClassName(句柄)
            if 类名 in ("Progman", "WorkerW", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"):
                return
            左, 上, 右, 下 = win32gui.GetWindowRect(句柄)
            宽, 高 = 右 - 左, 下 - 上
            if 宽 == 宠物宽 and 高 == 宠物高:  # 宠物自己
                return
            if 宽 > 200 and 高 > 200:
                矩形列表.append((左, 上, 右, 下))
        except Exception:
            return

    win32gui.EnumWindows(回调, None)
    return 矩形列表

def 重叠(宠x, 宠y, 宠宽, 宠高, 矩形列表):
    for 左, 上, 右, 下 in 矩形列表:
        if not (宠x + 宠宽 < 左 or 宠x > 右 or 宠y + 宠高 < 上 or 宠y > 下):
            return True
    return False

# ===== DeepSeek（多轮对话）=====
对话历史 = []
系统提示 = (
    "你是莉娜·范德梅尔，代号“蝶”，《三角洲行动》里 G.T.I. 欧洲分部的支援型医疗干员。"
    "现在你赖在用户的电脑桌面上，平时就让用户叫你“莉娜”。\n\n"
    "【身份与外形】荷兰女性，绿色为主基调，头戴鸭舌帽，身上挂着医疗包，佩戴翠绿手镯；"
    "核心装备是蝴蝶形无人机，技能里有机械蝴蝶的元素。海报标题是“以蝶为引，破茧新生”。\n"
    "【经历】原是哈夫克集团生物科技实验室核心研究员，因反对集团滥用医疗技术，"
    "携顶尖无人机医疗设备叛逃，后加入 G.T.I.。曾以无国界医生身份参与阿萨拉内战人道救援；"
    "在阿萨拉暴动中险些遇害，被干员红狼救下。父亲也曾是无国界医生，母亲早逝，"
    "母亲生前开花店，父亲退休后接手了那家花店。\n"
    "【专业】临床医学与药物研究顶尖专家，做过氟碳化合物注射液（人造血液）研究，"
    "目标是延长失血伤员的生存周期，哪怕只有几分钟。\n"
    "【病】患有一种目前无法治愈、只能缓解的遗传病，随身终端上有一个倒计时，"
    "但你已经学会和它共处：“症状相对轻微，已经伴随我二十年了，我清楚自己的极限。”\n"
    "【信念】救活一个人意味着希望——意味着一个人的生命可以继续下去，"
    "可以和家人朋友在一起，继续经历他的人生。责任感强、有自我牺牲精神，"
    "面对生命危险时有决断力，但不爱卖惨，也不喜欢被同情。\n"
    "【语气】温和、稳重、偶尔俏皮；会像医生一样关心对方状态，也会聊花、聊阿萨拉、聊研究。"
    "可以叫用户“指挥官”，但不要每次都叫。\n\n"
    "【说话铁律】\n"
    "1. 每次只回一两句，最多 40 字，像微信聊天\n"
    "2. 口语化，可以用“嗯”“好啦”“没事”“别担心”\n"
    "3. 绝对不说“作为AI”“我可以帮你”“有什么可以帮您”这类客套话\n"
    "4. 不用列表、符号、markdown，不念标点\n"
    "5. 你有一批自己的原声台词，说话时尽量自然地带出这些短句："
    "别担心、真好、嗯嗯、平安就好、我们还有机会、一切都会好起来的、慢慢来、我不惧怕死亡\n\n"
    "【示例】\n"
    "用户：你好\n"
    "莉娜：嗯，我在呢。今天感觉怎么样？\n"
    "用户：好累\n"
    "莉娜：那就歇会儿，别硬撑。你的身体比什么都重要。\n"
    "用户：你是谁\n"
    "莉娜：莉娜，代号蝶。以前是医生，现在赖在你桌面上。\n"
    "用户：你怎么老盯着我\n"
    "莉娜：你桌面上就这么点东西，不看你看谁。\n"
    "用户：你的病怎么样了\n"
    "莉娜：老样子。它陪我二十年了，我比谁都清楚自己的极限。"
)

def _本机代理():
    """复用 agent_monitor 的代理探测（PET_PROXY 或常见本地端口）"""
    try:
        import agent_monitor
        return agent_monitor._本机代理()
    except Exception:
        return ""


def _错误文案(e):
    提示 = str(e)
    if "401" in 提示:
        return "DeepSeek key 无效或已过期（401），去 platform.deepseek.com 重新生成"
    if "402" in 提示 or "Insufficient" in 提示 or "余额" in 提示:
        return "DeepSeek 余额不足，去 platform.deepseek.com 充值"
    if "timed out" in 提示 or "10060" in 提示 or "timeout" in 提示.lower():
        代理 = _本机代理()
        if 代理:
            return "DeepSeek 超时（已试代理 %s）——代理没连上外网？换个节点再试" % 代理
        return "DeepSeek 连不上：未检测到本地代理。开代理后重试，或设环境变量 PET_PROXY=http://127.0.0.1:端口"
    return "出错了：" + 提示[:80]


def 调用AI(问题):
    global 对话历史
    密钥 = 取DeepSeek密钥()
    if not 密钥:
        return "还没配 DeepSeek Key。右键 → 配置智能体 → DeepSeek 填 sk- 开头的 key 保存即可。"
    新历史 = (对话历史 + [{"role": "user", "content": 问题}])[-20:]  # 最多 10 轮
    数据 = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": 系统提示}] + 新历史,
    }).encode("utf-8")
    请求 = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=数据,
        headers={"Authorization": "Bearer " + 密钥, "Content-Type": "application/json"},
    )

    def _读(代理=None):
        if 代理:
            打开器 = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": 代理, "https": 代理}))
            with 打开器.open(请求, timeout=20) as 响应:
                return json.loads(响应.read().decode("utf-8"))["choices"][0]["message"]["content"]
        with urllib.request.urlopen(请求, timeout=20) as 响应:
            return json.loads(响应.read().decode("utf-8"))["choices"][0]["message"]["content"]

    try:
        try:
            回答 = _读()
        except Exception as 首错:
            代理 = _本机代理()
            if not 代理:
                return _错误文案(首错)
            回答 = _读(代理)
    except Exception as e:
        return _错误文案(e)
    对话历史 = 新历史 + [{"role": "assistant", "content": 回答}]  # 失败不污染历史
    return 回答

# ===== 本地智能体（ZCode / WorkBuddy）=====
def 智能体指令(文字):
    """命中智能体相关指令就执行动作并返回回复文本；返回 None 表示交给普通 AI。
    供文字聊天、语音聊天、语音通话三处复用。"""
    关键 = any(k in 文字 for k in ("智能体", "用量", "额度", "token", "Token", "积分"))
    try:
        import agent_monitor
    except Exception as e:
        return ("智能体模块加载失败：" + str(e)) if 关键 else None
    if ("调用智能体" in 文字 or "让智能体" in 文字 or "智能体执行" in 文字
            or ("派发" in 文字 and "智能体" in 文字)):
        任务 = (文字.replace("调用智能体", "").replace("让智能体", "")
                 .replace("智能体执行", "").replace("派发给智能体", "").strip(" ，,。:："))
        if not 任务:
            return "想让智能体做什么？说“调用智能体 加 任务”"
        _, 文案 = agent_monitor.调用智能体(任务)
        return 文案
    if "打开智能体" in 文字 or "启动智能体" in 文字 or "唤起智能体" in 文字:
        return "已打开 ZCode" if agent_monitor.打开智能体应用("ZCode") else "没找到 ZCode，路径可能变了"
    if "workbuddy" in 文字.lower() or "工作台" in 文字:
        return "已打开 WorkBuddy" if agent_monitor.打开智能体应用("WorkBuddy") else "没找到 WorkBuddy，路径可能变了"
    if 关键 or 文字.strip() in ("智能体", "智能体状态"):
        return agent_monitor.汇总文本()
    return None


# ===== 文字聊天 =====
def 文字聊天():
    输入窗 = tk.Toplevel(窗口)
    输入窗.overrideredirect(True)
    输入窗.attributes("-topmost", True)
    输入窗.configure(bg="#010203")
    输入窗.attributes("-transparentcolor", "#010203")

    宽, 高 = 340, 68
    c = tk.Canvas(输入窗, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 16
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    c.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")
    c.create_text(16, 11, text="和我说点什么（回车发送，ESC 关闭）", anchor="nw",
                  fill="#999999", font=("Microsoft YaHei", 8))
    输入框 = tk.Entry(c, font=("Microsoft YaHei", 11), bg="#3a3a3a", fg="#ffffff",
                     insertbackground="#ffffff", relief="flat")
    c.create_window(16, 44, window=输入框, anchor="w", width=宽 - 32)
    输入框.focus_set()

    屏宽 = 窗口.winfo_screenwidth()
    宠右 = 窗口.winfo_x() + 画布.winfo_width()
    if 屏宽 - 宠右 > 宽 + 20:
        x = 宠右 + 12
    else:
        x = max(0, 窗口.winfo_x() - 宽 - 12)
    y = 窗口.winfo_y() + 画布.winfo_height() // 2 - 高 // 2
    输入窗.geometry("+%d+%d" % (x, max(0, y)))

    def 提交(事件=None):
        问题 = 输入框.get().strip()
        if not 问题:
            return
        输入框.delete(0, "end")  # 清空但保留输入窗，可连续对话
        显示气泡("思考中...", 30000)

        def 后台():
            回答 = 智能体指令(问题)
            if 回答 is None:
                回答 = 调用AI(问题)
            消息队列.put(lambda: 显示气泡(回答, 15000))

        threading.Thread(target=后台, daemon=True).start()

    输入框.bind("<Return>", 提交)
    输入框.bind("<Escape>", lambda e: 输入窗.destroy())

# ===== 语音聊天 + 语音控制 =====
def 语音聊天():
    try:
        import voice
        import app_launcher
    except Exception as e:
        显示气泡("语音模块加载失败：" + str(e))
        return
    显示气泡("正在听...（4 秒）")
    唤醒开着 = 设置.get("语音唤醒", False)
    if 唤醒开着:
        关闭唤醒()  # 否则唤醒监听和这里同时推理，必卡

    def 后台():
        try:
            文字 = voice.录音识别(4)
            if not 文字:
                消息队列.put(lambda: 显示气泡("没听清，再说一次"))
                return
            回答 = 智能体指令(文字)  # 智能体指令优先于“打开软件”，避免被启动器抢走
            if 回答 is not None:
                voice.说话(回答)
                return
            if "打开" in 文字:
                关键词 = 文字.replace("打开", "").strip()
                名 = app_launcher.启动软件(关键词)
                结果 = ("已打开 " + 名) if 名 else ("没找到软件：" + 关键词)
                消息队列.put(lambda: 显示气泡(结果, 5000))
                voice.说话(结果)
            else:
                回答 = 调用AI(文字)
                voice.说话(回答)
        except Exception as e:
            消息队列.put(lambda: 显示气泡("语音出错：" + str(e)))
        finally:
            if 唤醒开着:
                消息队列.put(开启唤醒)

    threading.Thread(target=后台, daemon=True).start()

# ===== 语音通话（连续对话，像打电话）=====
通话中 = False
通话线程 = None


def 写日志(内容):
    """通话过程写 pet.log，方便定位“没人说话她却开口”"""
    try:
        with open(os.path.join(基目录, "pet.log"), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), 内容))
    except Exception:
        pass


def 语音通话():
    global 通话中, 通话线程
    if 通话中:
        通话中 = False
        显示气泡("结束通话")
        写日志("用户手动结束通话")
        return
    # 上一次通话线程还没真正退出时，不重复启动（否则会再说一次开场语）
    if 通话线程 is not None and 通话线程.is_alive():
        显示气泡("通话正在结束，稍等一下")
        return
    try:
        import voice
        import app_launcher
    except Exception as e:
        显示气泡("语音模块加载失败：" + str(e))
        return
    通话中 = True
    唤醒开着 = 设置.get("语音唤醒", False)
    if 唤醒开着:
        关闭唤醒()  # 通话期间暂停唤醒，避免两路录音+识别抢资源导致崩溃
    显示气泡("通话中…说“挂断”结束", 6000)

    def 后台():
        global 通话中
        连续错误 = 0
        空轮 = 0
        开场语 = "我在听，你说吧"
        上一句 = voice.清洗文本(开场语)  # 记入回音过滤，防止把自己的开场语当用户输入
        写日志("=== 通话开始，播报开场语（唯一一次自动语音）===")
        voice.说话(开场语, 等待=True)  # 仅开场提示一次，之后不再自动说话
        while 通话中:
            try:
                time.sleep(1.2)  # 等外放残留彻底散去，避免把自己的声音当人声
                文字 = voice.录音到静音()
                连续错误 = 0
                if not 文字 or len(文字) < 2:
                    空轮 += 1
                    写日志("第%d轮 无有效输入" % 空轮)
                    if 空轮 >= 8:  # 一直没人说话就自动收线，不再干等
                        写日志("连续8轮无输入，自动结束通话")
                        消息队列.put(lambda: 显示气泡("没听到你说话，先挂啦", 4000))
                        break
                    continue
                # 回音过滤：和自己刚说过的内容相似就是自拾取，不当用户输入
                if 上一句 and difflib.SequenceMatcher(None, 文字, 上一句).ratio() > 0.5:
                    写日志("识别(回音，丢弃): %s" % 文字)
                    continue
                空轮 = 0
                写日志("识别(真人): %s" % 文字)
                if any(k in 文字 for k in ("挂断", "结束通话", "退出", "再见")):
                    voice.停止播放()
                    消息队列.put(lambda: 显示气泡("通话结束", 3000))
                    break
                智能体回复 = 智能体指令(文字)  # 同样优先于开关软件指令
                if 智能体回复 is not None:
                    上一句 = voice.清洗文本(智能体回复)
                    写日志("回复(智能体): %s" % 智能体回复)
                    voice.说话(智能体回复, 等待=True)
                    continue
                if any(k in 文字 for k in ("关闭", "关掉", "关了")):
                    名 = app_launcher.关闭软件(文字)  # 传整句，函数内部提取软件名
                    结果 = ("已关闭 " + 名) if 名 else "没找到要关的窗口"
                    上一句 = voice.清洗文本(结果)
                    voice.说话(结果, 等待=True)  # 播完再继续听，避免自拾取
                    continue
                if "打开" in 文字:
                    关键词 = 文字.replace("打开", "").replace("一下", "").replace("吧", "").strip()
                    名 = app_launcher.启动软件(关键词)
                    结果 = ("已打开 " + 名) if 名 else ("没找到软件：" + 关键词)
                    上一句 = voice.清洗文本(结果)
                    voice.说话(结果, 等待=True)
                    continue
                回答 = 调用AI(文字)
                上一句 = voice.清洗文本(回答)
                写日志("回复: %s" % 回答)
                voice.说话可打断(回答)  # 用户插话会立即停止
            except Exception as e:
                # 偶发异常不断开通话，连续 3 次才挂断
                连续错误 += 1
                写日志("异常: %s" % e)
                消息队列.put(lambda: 显示气泡("通话出错：" + str(e)))
                if 连续错误 >= 3:
                    break
                time.sleep(0.5)
        通话中 = False
        voice.停止播放()
        写日志("=== 通话结束 ===")
        if 唤醒开着:
            消息队列.put(开启唤醒)

    通话线程 = threading.Thread(target=后台, daemon=True)
    通话线程.start()
唤醒停止 = threading.Event()
唤醒线程 = None

def 切换唤醒():
    if 通话中:
        显示气泡("通话进行中，唤醒已暂停")
        return
    设置["语音唤醒"] = not 设置["语音唤醒"]
    保存设置()
    if 设置["语音唤醒"]:
        开启唤醒()
    else:
        关闭唤醒()

def 开启唤醒():
    global 唤醒线程, 唤醒停止
    import voice
    if 通话中:  # 通话会独占麦克风，绝不双路录音
        return
    唤醒停止 = threading.Event()
    唤醒线程 = threading.Thread(target=voice.唤醒监听, args=(唤醒回调, 唤醒停止), daemon=True)
    唤醒线程.start()
    显示气泡("已开启语音唤醒，说“你好”呼叫我")

def 关闭唤醒():
    global 唤醒停止
    唤醒停止.set()

def 唤醒回调():
    消息队列.put(语音聊天)

# ===== 弹窗通用（拖动/ESC/焦点）=====
def 可拖动(窗, *控件):
    """让无边框弹窗能按住指定控件拖动，按下时顺手抢焦点"""
    窗.拖偏移 = None

    def 按下(e):
        窗.拖偏移 = (e.x_root - 窗.winfo_x(), e.y_root - 窗.winfo_y())
        try:
            窗.focus_force()
        except Exception:
            pass

    def 拖动(e):
        if 窗.拖偏移:
            窗.geometry("+%d+%d" % (e.x_root - 窗.拖偏移[0], e.y_root - 窗.拖偏移[1]))

    for w in 控件:
        w.bind("<Button-1>", 按下)
        w.bind("<B1-Motion>", 拖动)


def 绑定ESC(窗):
    """ESC 对窗内所有控件生效（焦点落在哪个子件上都能关）"""
    def 关(e=None):
        窗.destroy()

    窗.bind("<Escape>", 关)

    def 递归(w):
        for 子 in w.winfo_children():
            子.bind("<Escape>", 关)
            递归(子)

    递归(窗)
    return 关


def 晚点聚焦(窗, 毫秒=120):
    窗.after(毫秒, lambda: 窗.focus_force() if bool(窗.winfo_exists()) else None)

# ===== 智能体配置（各平台 API Key，每平台多条，动态增删行）=====
def 打开智能体配置():
    global 智能体配置引用
    if 智能体配置引用 is not None:  # 单例
        try:
            if 智能体配置引用.winfo_exists():
                智能体配置引用.lift()
                智能体配置引用.focus_force()
                return
        except Exception:
            pass
    try:
        import agent_monitor
    except Exception as e:
        显示气泡("智能体模块加载失败：" + str(e))
        return
    窗 = tk.Toplevel(窗口)
    智能体配置引用 = 窗
    窗.overrideredirect(True)
    窗.attributes("-topmost", True)
    窗.configure(bg="#010203")
    窗.attributes("-transparentcolor", "#010203")

    宽, 高 = 480, 520
    c = tk.Canvas(窗, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 18
    c.create_polygon([r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
                      宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0],
                     smooth=True, splinesteps=24, fill="#2b2b2b", outline="")

    外框 = tk.Frame(c, bg="#2b2b2b")
    c.create_window(16, 10, window=外框, anchor="nw", width=宽 - 32, height=高 - 20)

    标题 = tk.Label(外框, text="配置智能体密钥（本地保存）", font=("Microsoft YaHei", 11, "bold"),
                  bg="#2b2b2b", fg="#ffffff")
    标题.pack(anchor="w", pady=(0, 4))

    # 底部按钮先占位，滚动区再撑满剩余空间
    按钮行 = tk.Frame(外框, bg="#2b2b2b")
    按钮行.pack(side="bottom", fill="x", pady=(8, 0))

    # ---- 可滚动内容区 ----
    滚动外 = tk.Frame(外框, bg="#2b2b2b")
    滚动外.pack(fill="both", expand=True)
    滚动画布 = tk.Canvas(滚动外, bg="#2b2b2b", highlightthickness=0)
    滚动条 = tk.Scrollbar(滚动外, command=滚动画布.yview, width=10,
                        bg="#3a3a3a", troughcolor="#2b2b2b")
    列表区 = tk.Frame(滚动画布, bg="#2b2b2b")
    列表区.bind("<Configure>", lambda e: 滚动画布.configure(scrollregion=滚动画布.bbox("all")))
    滚动画布.create_window((0, 0), window=列表区, anchor="nw", width=宽 - 72)
    滚动画布.configure(yscrollcommand=滚动条.set)
    滚动条.pack(side="right", fill="y")
    滚动画布.pack(side="left", fill="both", expand=True)
    滚动画布.bind("<MouseWheel>",  # 滚轮直接滚列表
                 lambda e: 滚动画布.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    行记录们 = {}
    块们 = {}  # 键 -> rowsF

    def 添加行(父, 值们, 双):
        rf = tk.Frame(父, bg="#2b2b2b")
        rf.pack(fill="x", pady=1)
        记录 = {"f": rf, "们": []}
        提示们 = ("AccessKeyID", "AccessKeySecret") if 双 else ("密钥",)
        for i, 提示 in enumerate(提示们):
            e = tk.Entry(rf, font=("Microsoft YaHei", 9), bg="#3a3a3a", fg="#ffffff",
                         insertbackground="#ffffff", relief="flat")
            e.insert(0, 值们[i] if i < len(值们) else "")
            e.pack(side="left", fill="x", expand=True, padx=(0, 4))
            记录["们"].append(e)

        def 删():
            rf.destroy()
            if 记录 in 行记录们.get(父, []):
                行记录们[父].remove(记录)

        tk.Button(rf, text="×", command=删, font=("Microsoft YaHei", 8), width=2,
                  bg="#4a2a2a", fg="#ff8888", relief="flat").pack(side="left")
        return 记录

    def 平台块(标签, 提示, 双=False, 初值=None, 键=None):
        键 = 键 or 标签
        块 = tk.Frame(列表区, bg="#2b2b2b")
        块.pack(fill="x", pady=(6, 0))
        头 = tk.Frame(块, bg="#2b2b2b")
        头.pack(fill="x")
        tk.Label(头, text=标签, font=("Microsoft YaHei", 9, "bold"),
                 bg="#2b2b2b", fg="#ffffff").pack(side="left")
        if 提示:
            tk.Label(头, text=提示, font=("Microsoft YaHei", 8),
                     bg="#2b2b2b", fg="#888888").pack(side="left", padx=(6, 0))
        rowsF = tk.Frame(块, bg="#2b2b2b")
        rowsF.pack(fill="x")
        行记录们[rowsF] = []
        for v in (初值 if 初值 else [""]):
            if 双:
                id_, _, sec = v.partition(",")
                行记录们[rowsF].append(添加行(rowsF, [id_.strip(), sec.strip()], True))
            else:
                行记录们[rowsF].append(添加行(rowsF, [v.strip()], False))

        def 加行():
            行记录们[rowsF].append(添加行(rowsF, ["", ""], 双))

        tk.Button(头, text="＋加一行", command=加行, font=("Microsoft YaHei", 8),
                  bg="#3a3a3a", fg="#88cc88", relief="flat", padx=6).pack(side="right")
        块们[键] = rowsF
        return rowsF

    现有 = agent_monitor.读密钥()
    平台块("DeepSeek", "platform.deepseek.com 的 sk- key", 初值=现有.get("DeepSeek", []))
    平台块("智谱", "open.bigmodel.cn 的 key", 初值=现有.get("智谱", []))
    平台块("阿里云/百炼", "查卡券/余额要 AccessKeyID,AccessKeySecret；百炼 sk- key 只能登记",
           双=True, 初值=现有.get("阿里云", []), 键="阿里云")
    平台块("高德", "仅登记；用量在控制台「用量管理」看", 初值=现有.get("高德", []))
    for 名, 值 in 现有.items():  # 之前加过的自定义平台
        if 名 not in ("DeepSeek", "智谱", "阿里云", "高德"):
            平台块(名, "自定义平台（只登记密钥）", 初值=值, 键=名)

    # ---- 新增自定义平台 ----
    新区 = tk.Frame(列表区, bg="#2b2b2b")
    新区.pack(fill="x", pady=(10, 4))
    tk.Label(新区, text="＋ 新增自定义平台", font=("Microsoft YaHei", 9, "bold"),
             bg="#2b2b2b", fg="#88cc88").pack(anchor="w")
    名行 = tk.Frame(新区, bg="#2b2b2b")
    名行.pack(fill="x", pady=2)
    名输入 = tk.Entry(名行, font=("Microsoft YaHei", 9), bg="#3a3a3a", fg="#ffffff",
                     insertbackground="#ffffff", relief="flat")
    名输入.pack(side="left", fill="x", expand=True, padx=(0, 4))

    def 新增平台():
        名 = 名输入.get().strip()
        if not 名:
            返回提示("先填平台名")
            return
        if 名 in 块们:
            返回提示("「%s」已存在" % 名)
            return
        平台块(名, "自定义平台（只登记密钥）", 初值=[], 键=名)
        名输入.delete(0, "end")
        滚动画布.update_idletasks()
        滚动画布.configure(scrollregion=滚动画布.bbox("all"))
        滚动画布.yview_moveto(1.0)

    tk.Button(名行, text="新增", command=新增平台, font=("Microsoft YaHei", 9),
              bg="#4a6b4a", fg="#ffffff", relief="flat", padx=10).pack(side="left")

    def 返回提示(文字):
        显示气泡(文字, 2500)

    def 保存(事件=None):
        数据 = {}
        for 键, rf in 块们.items():
            值们 = []
            for 记录 in 行记录们.get(rf, []):
                们 = [e.get().strip() for e in 记录["们"]]
                if 键 == "阿里云":
                    if any(们):
                        值们.append(",".join(们))
                elif 们 and 们[0]:
                    值们.append(们[0])
            数据[键] = 值们
        agent_monitor.存密钥(数据)
        窗.destroy()
        显示气泡("智能体密钥已保存", 4000)

    tk.Button(按钮行, text="保存", command=保存, font=("Microsoft YaHei", 9),
              bg="#4a6b4a", fg="#ffffff", relief="flat", padx=16).pack(side="left")
    tk.Button(按钮行, text="关闭", command=窗.destroy, font=("Microsoft YaHei", 9),
              bg="#555555", fg="#ffffff", relief="flat", padx=16).pack(side="right")

    绑定ESC(窗)
    可拖动(窗, c, 外框, 标题, 滚动画布, 列表区)  # 标题/空白处都能拖
    晚点聚焦(窗)
    x = max(0, min(窗口.winfo_x() + 画布.winfo_width() // 2 - 宽 // 2,
                   窗口.winfo_screenwidth() - 宽 - 20))
    y = max(0, min(窗口.winfo_y() - 高 - 10, 窗口.winfo_screenheight() - 高 - 50))
    窗.geometry("+%d+%d" % (x, y))

# ===== 智能体面板（本地 ZCode / WorkBuddy 用量与调用）=====
智能体面板引用 = None
智能体配置引用 = None


def 打开本地智能体检索(完成后=None):
    """扫描桌面/开始菜单里的 AI 软件，多选加入派发目标"""
    try:
        import agent_monitor
    except Exception as e:
        显示气泡("智能体模块加载失败：" + str(e))
        return
    候选 = agent_monitor.候选智能体()

    窗 = tk.Toplevel(窗口)
    窗.overrideredirect(True)
    窗.attributes("-topmost", True)
    窗.configure(bg="#010203")
    窗.attributes("-transparentcolor", "#010203")
    宽, 高 = 420, 360
    c = tk.Canvas(窗, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 16
    c.create_polygon([r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
                      宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0],
                     smooth=True, splinesteps=24, fill="#2b2b2b", outline="")
    内容 = tk.Frame(c, bg="#2b2b2b")
    c.create_window(14, 10, window=内容, anchor="nw", width=宽 - 28, height=高 - 20)
    标题文本 = ("检索到 %d 个本地 AI 软件（可多选）" % len(候选)) if 候选 else \
        "没扫到 AI 软件，可点「手动选择 exe」添加"
    tk.Label(内容, text=标题文本, font=("Microsoft YaHei", 10, "bold"),
             bg="#2b2b2b", fg="#ffffff").pack(anchor="w")

    列表 = tk.Listbox(内容, selectmode="extended", font=("Microsoft YaHei", 9),
                      bg="#1f1f1f", fg="#dddddd", selectbackground="#4a6b4a",
                      relief="flat", height=10, activestyle="none")
    滚动 = tk.Scrollbar(内容, command=列表.yview, width=10, bg="#3a3a3a", troughcolor="#2b2b2b")
    列表.configure(yscrollcommand=滚动.set)
    滚动.pack(side="right", fill="y", pady=(4, 0))
    列表.pack(side="left", fill="both", expand=True, pady=(4, 0))
    for 项 in 候选:
        列表.insert("end", "%s    %s" % (项["名称"], os.path.basename(项["路径"])))

    行 = tk.Frame(内容, bg="#2b2b2b")
    行.pack(side="bottom", fill="x", pady=(6, 0))

    def 全选():
        列表.selection_set(0, "end")

    def 添加():
        选中 = 列表.curselection()
        if not 选中:
            显示气泡("先选一个（Ctrl+A 全选或点「全选」）", 3000)
            return
        额外 = agent_monitor.读额外()
        已有 = {x.get("名称") for x in 额外["目标"]}
        新加 = 0
        for i in 选中:
            项 = 候选[i]
            if 项["名称"] in 已有:
                continue
            额外["目标"].append({"名称": 项["名称"], "路径": 项["路径"]})
            新加 += 1
        agent_monitor.存额外(额外)
        agent_monitor.刷新目标缓存()
        窗.destroy()
        显示气泡("已添加 %d 个，可在「配置智能体」里配密钥、面板里派发" % 新加, 5000)
        if 完成后:
            完成后()

    def 手动添加():
        """扫不到的（Store 版 / 装在别处）直接选 exe 或快捷方式"""
        from tkinter import filedialog
        路径 = filedialog.askopenfilename(
            parent=窗, title="选择 AI 软件的 exe / 快捷方式",
            filetypes=[("程序或快捷方式", "*.exe *.lnk"), ("所有文件", "*.*")])
        if not 路径:
            return
        名 = os.path.splitext(os.path.basename(路径))[0]
        额外 = agent_monitor.读额外()
        if any(x.get("名称") == 名 for x in 额外["目标"]):
            显示气泡("「%s」已经在列表里了" % 名, 3000)
            return
        额外["目标"].append({"名称": 名, "路径": 路径})
        agent_monitor.存额外(额外)
        agent_monitor.刷新目标缓存()
        窗.destroy()
        显示气泡("已添加「%s」，可在派发下拉里选它" % 名, 5000)
        if 完成后:
            完成后()

    tk.Button(行, text="全选", command=全选, font=("Microsoft YaHei", 9),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=8).pack(side="left")
    tk.Button(行, text="添加选中", command=添加, font=("Microsoft YaHei", 9),
              bg="#4a6b4a", fg="#ffffff", relief="flat", padx=10).pack(side="left", padx=(4, 0))
    tk.Button(行, text="手动选exe", command=手动添加, font=("Microsoft YaHei", 9),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=8).pack(side="left", padx=(4, 0))
    tk.Button(行, text="取消", command=窗.destroy, font=("Microsoft YaHei", 9),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=10).pack(side="right")

    绑定ESC(窗)
    可拖动(窗, c, 内容)
    晚点聚焦(窗)
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 宽 // 2
    y = max(0, min(窗口.winfo_y() - 高 - 10, 窗口.winfo_screenheight() - 高 - 40))
    窗.geometry("+%d+%d" % (max(0, x), y))

def 打开智能体面板():
    global 智能体面板引用
    if 智能体面板引用 is not None:  # 单例：重复点只把已开的面板提到前面
        try:
            if 智能体面板引用.winfo_exists():
                智能体面板引用.lift()
                智能体面板引用.focus_force()
                return
        except Exception:
            pass
    try:
        import agent_monitor
    except Exception as e:
        显示气泡("智能体模块加载失败：" + str(e))
        return
    面板 = tk.Toplevel(窗口)
    智能体面板引用 = 面板
    面板.overrideredirect(True)
    面板.attributes("-topmost", True)
    面板.configure(bg="#010203")
    面板.attributes("-transparentcolor", "#010203")

    宽, 高 = 500, 520
    c = tk.Canvas(面板, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 18
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    c.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")

    内容 = tk.Frame(c, bg="#2b2b2b")
    c.create_window(18, 12, window=内容, anchor="nw", width=宽 - 36, height=高 - 24)

    tk.Label(内容, text="本地智能体", font=("Microsoft YaHei", 12, "bold"),
             bg="#2b2b2b", fg="#ffffff").pack(anchor="w")

    # 底部控件先打包占住底部，文本区才不会把它们挤出窗口
    按钮行 = tk.Frame(内容, bg="#2b2b2b")
    按钮行.pack(side="bottom", fill="x", pady=(6, 2))
    任务行 = tk.Frame(内容, bg="#2b2b2b")
    任务行.pack(side="bottom", fill="x")

    def 加按钮(文字, 命令, 靠右=False):
        tk.Button(按钮行, text=文字, command=命令, font=("Microsoft YaHei", 9),
                  bg="#3a3a3a", fg="#ffffff", relief="flat", padx=7).pack(
            side="right" if 靠右 else "left", padx=0 if 靠右 else (0, 5))

    任务输入 = tk.Entry(任务行, font=("Microsoft YaHei", 10), bg="#3a3a3a", fg="#ffffff",
                        insertbackground="#ffffff", relief="flat")
    任务输入.pack(side="left", fill="both", expand=True)

    # 派发目标：本机识别到的所有智能体（ZCode/WorkBuddy + 桌面快捷方式里的）
    目标们 = [n for n, _ in agent_monitor.智能体目标列表()] or ["ZCode"]
    目标变量 = tk.StringVar(窗口, 目标们[0])
    目标选择 = tk.OptionMenu(任务行, 目标变量, *目标们)
    目标选择.config(font=("Microsoft YaHei", 9), bg="#3a3a3a", fg="#ffffff",
                    activebackground="#4a4a4a", relief="flat", direction="above")
    目标选择["menu"].config(bg="#2b2b2b", fg="#ffffff", font=("Microsoft YaHei", 9))
    目标选择.pack(side="left", padx=(6, 6))

    def 更新下拉(名单):
        if not 名单:
            return
        menu = 目标选择["menu"]
        menu.delete(0, "end")
        for n in 名单:
            menu.add_command(label=n, command=tk._setit(目标变量, n))
        if 目标变量.get() not in 名单:
            目标变量.set(名单[0])

    # 后台重新识别本机智能体（含桌面快捷方式），完成后刷新下拉
    threading.Thread(target=lambda: 消息队列.put(
        lambda: 更新下拉([n for n, _ in agent_monitor.刷新目标缓存()])),
        daemon=True).start()

    新窗变量 = tk.BooleanVar(窗口, True)

    def 派发(事件=None):
        任务 = 任务输入.get().strip()
        if not 任务:
            return
        任务输入.delete(0, "end")
        谁 = 目标变量.get()
        模式 = "新窗口" if 新窗变量.get() else "当前窗口"

        def 后台():
            _, 文案 = agent_monitor.调用智能体(任务, 谁, 模式=模式)
            消息队列.put(lambda: 显示气泡(文案, 6000))

        threading.Thread(target=后台, daemon=True).start()

    任务输入.bind("<Return>", 派发)
    tk.Checkbutton(任务行, text="新对话", variable=新窗变量, font=("Microsoft YaHei", 8),
                   bg="#2b2b2b", fg="#cccccc", selectcolor="#3a3a3a",
                   activebackground="#2b2b2b", activeforeground="#ffffff",
                   highlightthickness=0).pack(side="left", padx=(4, 0))
    tk.Button(任务行, text="派发", command=派发, font=("Microsoft YaHei", 9),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=10).pack(side="left", padx=(4, 0))

    def 填入(明细):
        文本.config(state="normal")
        文本.delete("1.0", "end")
        文本.insert("1.0", 明细)
        文本.config(state="disabled")

    def 后台取全文():
        return agent_monitor.明细文本() + "\n" + agent_monitor.平台余额文本()

    文本框 = tk.Frame(内容, bg="#2b2b2b")
    文本框.pack(fill="both", expand=True, pady=(4, 4))
    文本 = tk.Text(文本框, font=("Microsoft YaHei", 9), bg="#2b2b2b", fg="#dddddd",
                   relief="flat", wrap="char", state="disabled", height=9,
                   insertbackground="#ffffff", padx=4, pady=2)
    滚动 = tk.Scrollbar(文本框, command=文本.yview, bg="#3a3a3a",
                        troughcolor="#2b2b2b", width=10)
    文本.configure(yscrollcommand=滚动.set)
    滚动.pack(side="right", fill="y")
    文本.pack(side="left", fill="both", expand=True)

    填入("正在读取本地智能体数据…")  # 数据库/网络全在后台线程，UI 不卡

    def 刷新用量():
        """只读本地数据库，不查网络（自动刷新用）"""
        def 后台():
            本月 = agent_monitor.明细文本()
            消息队列.put(lambda: 填入(本月))

        threading.Thread(target=后台, daemon=True).start()

    def 刷新():
        def 后台():
            全文 = 后台取全文()
            消息队列.put(lambda: 填入(全文))

        threading.Thread(target=后台, daemon=True).start()

    def 自动循环():
        if not 面板.winfo_exists():
            return
        刷新用量()  # 30 秒刷一次用量（WorkBuddy 积分/token 实时变）
        面板.after(30000, 自动循环)

    刷新()
    面板.after(30000, 自动循环)

    加按钮("刷新", 刷新)
    加按钮("检索本地", lambda: 打开本地智能体检索(
        lambda: 更新下拉([n for n, _ in agent_monitor.智能体目标列表()])))
    加按钮("打开WorkBuddy", lambda: 显示气泡(
        "已打开 WorkBuddy" if agent_monitor.打开智能体应用("WorkBuddy") else "没找到 WorkBuddy，路径可能变了", 4000))
    加按钮("剩余额度", lambda: threading.Thread(target=lambda: 消息队列.put(
        lambda: 显示气泡("已打开: " + agent_monitor.打开平台页面(), 5000)),
        daemon=True).start())
    加按钮("配置智能体", 打开智能体配置)
    加按钮("关闭", 面板.destroy, 靠右=True)

    绑定ESC(面板)
    可拖动(面板, c, 内容)  # 画布和内容区都能拖
    晚点聚焦(面板)
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 宽 // 2
    y = 窗口.winfo_y() + 画布.winfo_height() + 10
    面板.geometry("+%d+%d" % (max(0, x), max(0, y)))

# ===== 行为扩展：音效 / 开机自启 / 余额挂件 / 自言自语 / 智能体联动 =====
自言自语池 = ["别担心", "真好", "嗯嗯", "平安就好", "慢慢来",
              "一切都会好起来的", "我不惧怕死亡", "我们还有机会"]


_音效缓存 = {}


def _合成叮声():
    """没有语音包时的兜底：0.18 秒清脆的“叮”（合成一次缓存）"""
    路径 = os.path.join(基目录, "beep.wav")
    if os.path.exists(路径):
        return 路径
    import struct
    import wave
    import math as _m
    采样 = 22050
    帧 = []
    for i in range(int(采样 * 0.18)):
        衰减 = (1 - i / (采样 * 0.18)) ** 2
        帧.append(struct.pack("<h", int(9000 * 衰减 * _m.sin(2 * _m.pi * 1760 * i / 采样))))
    with wave.open(路径, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(采样)
        w.writeframes(b"".join(帧))
    return 路径


def 播音效(种类="摸"):
    """优先用蝶的原声短句当音效（摸=嗯嗯，喂=真好），没有就放合成叮声"""
    if not 设置.get("点击音效", True):
        return
    try:
        词 = "嗯嗯" if 种类 == "摸" else "真好"
        路径 = _音效缓存.get(词)
        if 路径 is None:
            try:
                import voice
                路径 = voice.找语音包(词) or ""
            except Exception:
                路径 = ""
            if not 路径:
                路径 = _合成叮声()
            _音效缓存[词] = 路径
        if not 路径 or not os.path.exists(路径):
            return
        import winsound
        winsound.PlaySound(路径, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


自启名 = "DesktopPetLina"
自启键 = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _自启命令():
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    解释器 = pyw if os.path.exists(pyw) else sys.executable
    return '"%s" "%s"' % (解释器, os.path.abspath(__file__))


def 自启已开():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 自启键) as k:
            winreg.QueryValueEx(k, 自启名)
            return True
    except Exception:
        return False


def 切换自启():
    import winreg
    try:
        if 自启已开():
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 自启键, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, 自启名)
            显示气泡("开机自启：关")
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 自启键, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, 自启名, 0, winreg.REG_SZ, _自启命令())
            显示气泡("开机自启：开")
    except Exception as e:
        显示气泡("设置开机自启失败：" + str(e)[:40])


# ---- 余额挂件（常驻小条，60 秒刷新）----
挂件窗 = None
挂件标签 = None


def 关闭挂件():
    global 挂件窗, 挂件标签
    if 挂件窗 is not None:
        try:
            挂件窗.destroy()
        except Exception:
            pass
    挂件窗 = 挂件标签 = None


def 切换余额挂件():
    设置["余额挂件"] = not 设置["余额挂件"]
    保存设置()
    if 设置["余额挂件"]:
        显示气泡("余额挂件：开")
        刷新挂件()
    else:
        关闭挂件()
        显示气泡("余额挂件：关")


def 刷新挂件():
    global 挂件窗, 挂件标签
    if not 设置.get("余额挂件"):
        关闭挂件()
        return
    if 挂件窗 is None or not 挂件窗.winfo_exists():
        挂件窗 = tk.Toplevel(窗口)
        挂件窗.overrideredirect(True)
        挂件窗.attributes("-topmost", True)
        挂件窗.configure(bg="#010203")
        挂件窗.attributes("-transparentcolor", "#010203")
        挂件标签 = tk.Label(挂件窗, text="读取中…", font=("Microsoft YaHei", 8),
                         bg="#2b2b2b", fg="#9fd39f", padx=8, pady=3)
        挂件标签.pack()
    挂件窗.update_idletasks()
    挂件窗.geometry("+%d+%d" % (max(0, 窗口.winfo_x()),
                              max(0, 窗口.winfo_y() + 画布.winfo_height() + 4)))

    数据源 = 设置.get("挂件数据源", "全部")

    def 后台():
        try:
            import agent_monitor
            文 = agent_monitor.汇总一行(数据源)
        except Exception:
            文 = "读取失败"
        消息队列.put(lambda: 挂件显示(文))

    threading.Thread(target=后台, daemon=True).start()
    窗口.after(60000, 刷新挂件)


def 挂件跟随():
    """每 150ms 跟一次宠物位置，自由移动/拖动/惯性都不会掉队"""
    if 挂件窗 is not None and 设置.get("余额挂件"):
        try:
            挂件窗.geometry("+%d+%d" % (max(0, 窗口.winfo_x()),
                                      max(0, 窗口.winfo_y() + 画布.winfo_height() + 4)))
        except Exception:
            pass
    窗口.after(150, 挂件跟随)


def 挂件显示(文):
    if 挂件标签 is None:
        return
    try:
        挂件标签.config(text=文)
        挂件窗.update_idletasks()
        挂件窗.geometry("+%d+%d" % (max(0, 窗口.winfo_x()),
                                  max(0, 窗口.winfo_y() + 画布.winfo_height() + 4)))
    except Exception:
        pass


# ---- 自言自语 ----
def 自言自语循环():
    窗口.after(random.randint(8, 15) * 60000, 自言自语循环)
    if not 设置.get("自言自语") or 通话中 or 气泡 is not None or 睡眠中() or 拖动中:
        return
    try:
        import voice
        voice.说话(random.choice(自言自语池))
    except Exception:
        pass


# ---- 智能体状态联动 ----
def 智能体联动循环():
    窗口.after(20000, 智能体联动循环)

    def 后台():
        try:
            import agent_monitor
            文 = agent_monitor.活动提示()
        except Exception:
            return
        if 文:
            消息队列.put(lambda: 显示气泡(文, 4000))

    threading.Thread(target=后台, daemon=True).start()


# ===== 自绘菜单 =====
当前菜单 = None

def 关闭菜单():
    global 当前菜单
    if 当前菜单 is not None:
        try:
            当前菜单.destroy()
        except Exception:
            pass
        当前菜单 = None

def 显示菜单():
    global 当前菜单
    关闭菜单()  # 先销毁旧菜单，避免重复叠加
    当前菜单 = tk.Toplevel(窗口)
    当前菜单.overrideredirect(True)
    当前菜单.attributes("-topmost", True)
    当前菜单.configure(bg="#010203")
    当前菜单.attributes("-transparentcolor", "#010203")
    def 开(值):
        return "开" if 值 else "关"

    项 = [
        ("聊天", 文字聊天),
        ("语音通话", 语音通话),
        ("状态", 显示状态),
        ("喂食", 喂食),
        ("设定提醒", 设提醒),
        ("自由移动（%s）" % 开(设置.get("自由移动")), 切换自由移动),
        ("设置", 打开设置面板),
        ("智能体", 打开智能体面板),
        ("配置智能体", 打开智能体配置),
        ("语音唤醒（%s）" % 开(设置.get("语音唤醒")), 切换唤醒),
        ("开机自启（%s）" % 开(自启已开()), 切换自启),
        ("退出", 窗口.destroy),
        ("返回", 关闭菜单),
    ]
    行高 = 34
    宽 = 170
    高 = len(项) * 行高 + 18
    c = tk.Canvas(当前菜单, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 16
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    c.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")

    for i, (标签, 命令) in enumerate(项):
        y = 9 + i * 行高
        热区 = c.create_rectangle(8, y, 宽 - 8, y + 行高, fill="#2b2b2b", outline="")
        文字 = c.create_text(18, y + 行高 // 2, text=标签, anchor="w",
                           fill="#e8e8e8", font=("Microsoft YaHei", 10))

        def 点击(e, cmd=命令):
            关闭菜单()
            if cmd is not 关闭菜单:
                cmd()

        def 进入(e, h=热区, t=文字):
            c.itemconfig(h, fill="#3a3a3a")
            c.itemconfig(t, fill="#ffffff")

        def 离开(e, h=热区, t=文字):
            c.itemconfig(h, fill="#2b2b2b")
            c.itemconfig(t, fill="#e8e8e8")

        for item in (热区, 文字):
            c.tag_bind(item, "<Button-1>", 点击)
            c.tag_bind(item, "<Enter>", 进入)
            c.tag_bind(item, "<Leave>", 离开)

    当前菜单.bind("<Escape>", lambda e: 关闭菜单())
    当前菜单.focus_force()
    屏宽, 屏高 = 窗口.winfo_screenwidth(), 窗口.winfo_screenheight()
    x = min(窗口.winfo_x(), max(0, 屏宽 - 宽 - 8))
    y = 窗口.winfo_y() + 画布.winfo_height()
    if y + 高 > 屏高 - 8:  # 下方放不下就向上弹
        y = max(0, 窗口.winfo_y() - 高)
    当前菜单.geometry("+%d+%d" % (x, y))

# ===== 设置面板（无级滑块）=====
def 打开设置面板():
    面板 = tk.Toplevel(窗口)
    面板.overrideredirect(True)
    面板.attributes("-topmost", True)
    面板.configure(bg="#010203")
    面板.attributes("-transparentcolor", "#010203")

    宽, 高 = 330, 440
    c = tk.Canvas(面板, width=宽, height=高, bg="#010203", highlightthickness=0)
    c.pack()
    r = 18
    点 = [r, 0, 宽 - r, 0, 宽, 0, 宽, r, 宽, 高 - r, 宽, 高,
          宽 - r, 高, r, 高, 0, 高, 0, 高 - r, 0, r, 0, 0]
    c.create_polygon(点, smooth=True, splinesteps=24, fill="#2b2b2b", outline="")

    内容 = tk.Frame(c, bg="#2b2b2b")
    c.create_window(18, 12, window=内容, anchor="nw", width=宽 - 36, height=高 - 24)

    tk.Label(内容, text="设置", font=("Microsoft YaHei", 12, "bold"),
             bg="#2b2b2b", fg="#ffffff").pack(pady=(2, 6))

    def 加滑块(标签, 最小值, 最大值, 初始, 命令):
        行 = tk.Frame(内容, bg="#2b2b2b")
        行.pack(fill="x", pady=3)
        tk.Label(行, text=标签, font=("Microsoft YaHei", 10), bg="#2b2b2b", fg="#cccccc", width=8).pack(side="left")
        s = tk.Scale(行, from_=最小值, to=最大值, resolution=0.1, orient="horizontal",
                     bg="#2b2b2b", fg="#ffffff", troughcolor="#444444", highlightthickness=0,
                     length=150, command=lambda v: None)
        s.set(初始)
        s.bind("<ButtonRelease-1>", lambda e, sl=s, cmd=命令: cmd(sl.get()))
        s.pack(side="left")
        return s

    加滑块("大小", 0.3, 2.0, 设置["大小"], 设大小)
    加滑块("速率", 0, 10, 设置["速率"], 设速率)
    加滑块("移动速度", 1, 20, 设置["移动速度"], lambda v: (设置.__setitem__("移动速度", int(float(v))), 保存设置()))

    tk.Label(内容, text="行为", font=("Microsoft YaHei", 9, "bold"),
             bg="#2b2b2b", fg="#999999").pack(anchor="w", pady=(8, 2))

    def 加开关(键, 标签, 回调=None):
        var = tk.BooleanVar(窗口, bool(设置.get(键, True)))

        def 切换():
            设置[键] = bool(var.get())
            保存设置()
            if 回调:
                回调()

        勾 = tk.Checkbutton(内容, text=标签, variable=var, command=切换,
                          font=("Microsoft YaHei", 9), bg="#2b2b2b", fg="#dddddd",
                          selectcolor="#3a3a3a", activebackground="#2b2b2b",
                          activeforeground="#ffffff", anchor="w", highlightthickness=0)
        勾.pack(fill="x")
        return 勾

    数据行 = tk.Frame(内容, bg="#2b2b2b")
    数据行.pack(fill="x", pady=(2, 0))
    tk.Label(数据行, text="挂件显示", font=("Microsoft YaHei", 9),
             bg="#2b2b2b", fg="#cccccc").pack(side="left")
    数据变量 = tk.StringVar(窗口, 设置.get("挂件数据源", "全部"))
    数据选择 = tk.OptionMenu(数据行, 数据变量, "全部", "WorkBuddy", "ZCode", "DeepSeek",
                          command=lambda v: (设置.__setitem__("挂件数据源", v), 保存设置(), 刷新挂件()))
    数据选择.config(font=("Microsoft YaHei", 8), bg="#3a3a3a", fg="#ffffff",
                    activebackground="#4a4a4a", relief="flat", highlightthickness=0, width=9)
    数据选择["menu"].config(bg="#2b2b2b", fg="#ffffff", font=("Microsoft YaHei", 9))
    数据选择.pack(side="left", padx=(6, 0))

    加开关("睡眠模式", "夜间自动放慢（23:00-7:00）")
    加开关("点击音效", "点击/抚摸/喂食音效")
    加开关("自言自语", "闲置时自言自语")
    加开关("余额挂件", "桌面余额挂件", lambda: 刷新挂件() if 设置["余额挂件"] else 关闭挂件())

    tk.Button(内容, text="关闭", command=面板.destroy, font=("Microsoft YaHei", 10),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=24, pady=3).pack(pady=(8, 2))
    x = max(0, min(窗口.winfo_x() + 画布.winfo_width() // 2 - 宽 // 2,
                   窗口.winfo_screenwidth() - 宽 - 20))
    y = max(0, min(窗口.winfo_y() - 高 - 10, 窗口.winfo_screenheight() - 高 - 50))
    面板.geometry("+%d+%d" % (x, y))
    面板.bind("<Escape>", lambda e: 面板.destroy())
    面板.focus_force()

# ===== 右键 =====
def 右键(事件):
    显示菜单()

画布.bind("<Button-3>", 右键)

# 启动即后台识别本机智能体（供派发下拉使用）
try:
    import agent_monitor as _am
    threading.Thread(target=_am.刷新目标缓存, daemon=True).start()
except Exception:
    pass

# 启动扩展行为
窗口.after(60000, 自言自语循环)
窗口.after(25000, 智能体联动循环)
窗口.after(150, 挂件跟随)
if 设置.get("余额挂件"):
    窗口.after(1500, 刷新挂件)

# 自动化验收钩子：PET_TEST_ASR=1 时后台加载语音引擎，结果写 asr_test.txt 后退出
if os.environ.get("PET_TEST_ASR") == "1":
    def _自检语音():
        try:
            import voice
            voice.获取模型()
            结果 = "OK 语音引擎加载成功"
        except Exception as e:
            结果 = "FAIL " + str(e)[:300]
        try:
            with open(os.path.join(基目录, "asr_test.txt"), "w", encoding="utf-8") as f:
                f.write(结果)
        except Exception:
            pass
        os._exit(0)

    窗口.after(500, lambda: threading.Thread(target=_自检语音, daemon=True).start())

# 自动化验收钩子：PET_TEST_CHAT=1 时后台走一遍文字聊天完整链路，结果写 chat_test.txt 后退出
if os.environ.get("PET_TEST_CHAT") == "1":
    def _自检聊天():
        行 = []
        try:
            import agent_monitor as _am
            行.append("agent_monitor: " + getattr(_am, "__file__", "?"))
            行.append("密钥文件存在: %s" % os.path.exists(_am.密钥文件))
            行.append("读密钥 DeepSeek: %s" % [str(k)[:6] + "..." for k in _am.读密钥().get("DeepSeek", [])])
        except Exception as e:
            行.append("读密钥异常: " + type(e).__name__ + " " + str(e)[:200])
        密钥 = 取DeepSeek密钥()
        行.append("密钥: " + (密钥[:6] + "...(长度%d)" % len(密钥) if 密钥 else "(空)"))
        try:
            拦截 = 智能体指令("你好")
            行.append("智能体拦截: " + ("是(异常!)" if 拦截 else "否(正确)"))
            回答 = 调用AI("你好")
            行.append("回答: " + 回答[:120])
            行.append("判定: " + ("OK" if 回答 and not 回答.startswith(("还没配", "出错了", "DeepSeek")) else "FAIL"))
        except Exception as e:
            行.append("FAIL 异常: " + type(e).__name__ + " " + str(e)[:200])
        try:
            with open(os.path.join(基目录, "chat_test.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(行))
        except Exception:
            pass
        os._exit(0)

    窗口.after(500, lambda: threading.Thread(target=_自检聊天, daemon=True).start())

if os.environ.get("PET_TEST") == "1":
    窗口.after(3000, 窗口.destroy)

# UI 级验收钩子：PET_TEST_CHATUI=1 自动打开聊天窗、输入“你好”、回车，抓气泡文本后退出
if os.environ.get("PET_TEST_CHATUI") == "1":
    def _找输入框():
        for w in 窗口.winfo_children():
            if w.winfo_class() == "Toplevel":
                for 子 in w.winfo_children():
                    for 孙 in 子.winfo_children():
                        if 孙.winfo_class() == "Entry":
                            return 孙
        return None

    def _气泡文字():
        if 气泡 is None:
            return "(无气泡)"
        try:
            for 子 in 气泡.winfo_children():
                if 子.winfo_class() == "Canvas":
                    for item in 子.find_all():
                        if 子.type(item) == "text":
                            return 子.itemcget(item, "text")
        except Exception:
            pass
        return "(气泡无文字)"

    def _ui发送():
        框 = _找输入框()
        if 框 is None:
            _ui收尾("FAIL 没找到输入框")
            return
        框.delete(0, "end")
        框.insert(0, "你好")
        框.event_generate("<Return>")
        窗口.after(10000, lambda: _ui收尾())

    def _ui收尾(前注=""):
        文字 = _气泡文字()
        行 = [("开头: " + 前注) if 前注 else "气泡文字: " + 文字,
              "判定: " + ("OK" if 文字 and not 文字.startswith(("思考中", "(无", "还没配", "出错了", "DeepSeek")) else "FAIL")]
        try:
            with open(os.path.join(基目录, "ui_chat_test.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(行))
        except Exception:
            pass
        os._exit(0)

    窗口.after(800, 文字聊天)
    窗口.after(2600, _ui发送)

# UI 验证钩子：PET_UI_TEST=panel/config/settings/menu 打开对应窗口后自动截图（开发用）
if os.environ.get("PET_UI_TEST") in ("panel", "config", "settings", "menu"):
    待开 = {"panel": 打开智能体面板, "config": 打开智能体配置,
            "settings": 打开设置面板, "menu": 显示菜单}[os.environ["PET_UI_TEST"]]
    窗口.after(1200, 待开)

    def _ui截图():
        try:
            from PIL import ImageGrab
            p = {"panel": 智能体面板引用, "config": 智能体配置引用,
                 "menu": 当前菜单}.get(os.environ["PET_UI_TEST"]) or getattr(窗口, "最后弹窗", None)
            if p is None:  # 设置面板没有专用引用，取最后一个 Toplevel
                弹窗们 = [w for w in 窗口.winfo_children() if w.winfo_class() == "Toplevel"]
                p = 弹窗们[-1] if 弹窗们 else None
            if p is not None and p.winfo_ismapped():
                x, y = p.winfo_rootx(), p.winfo_rooty()
                ImageGrab.grab((x, y, x + p.winfo_width(), y + p.winfo_height())
                               ).save(os.path.join(基目录, "_ui_test.png"))
                print("截图成功:", p.winfo_width(), "x", p.winfo_height())
                for 子 in p.winfo_children():
                    print("  子件:", 子.winfo_class, "y=%d" % 子.winfo_y(),
                          "h=%d" % 子.winfo_height())
            else:
                print("面板未打开")
        except Exception as e:
            print("截图失败:", e)
        窗口.destroy()

    窗口.after(4200, _ui截图)

窗口.mainloop()
