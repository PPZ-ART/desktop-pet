import os
import json
import random
import time
import queue
import threading
import urllib.request
import tkinter as tk
from PIL import Image, ImageTk

基目录 = os.path.dirname(os.path.abspath(__file__))
帧目录 = os.path.join(基目录, "frames")
设置文件 = os.path.join(基目录, "settings.json")
状态文件 = os.path.join(基目录, "pet_state.json")
DeepSeek密钥 = os.environ.get("DEEPSEEK_KEY", "")

# ===== 设置 =====
默认设置 = {"大小": 1.0, "速率": 70, "自由移动": False, "移动速度": 5, "语音唤醒": False}
设置 = dict(默认设置)
if os.path.exists(设置文件):
    try:
        设置.update(json.load(open(设置文件, encoding="utf-8")))
    except Exception:
        pass

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
帧间隔 = int(设置["速率"])
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
    窗口.after(帧间隔, 播放)

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
    气泡.configure(bg="#ffffff", highlightthickness=0)
    标签 = tk.Label(气泡, text=文字, font=("Microsoft YaHei", 10), bg="#ffffff", fg="#333333", padx=10, pady=6)
    标签.pack()
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 80
    y = 窗口.winfo_y() - 45
    气泡.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
    气泡.after(毫秒, 气泡.destroy)

# ===== 拖动 / 抚摸 =====
def 按下(事件):
    global 动画暂停
    窗口.偏移x = 事件.x_root - 窗口.winfo_x()
    窗口.偏移y = 事件.y_root - 窗口.winfo_y()
    窗口.按下x = 事件.x_root
    窗口.按下y = 事件.y_root
    动画暂停 = True

def 拖动(事件):
    x = 事件.x_root - 窗口.偏移x
    y = 事件.y_root - 窗口.偏移y
    窗口.geometry("+%d+%d" % (x, y))

def 松开(事件):
    global 动画暂停
    动画暂停 = False
    位移 = abs(事件.x_root - 窗口.按下x) + abs(事件.y_root - 窗口.按下y)
    if 位移 < 5:
        抚摸()

画布.bind("<Button-1>", 按下)
画布.bind("<B1-Motion>", 拖动)
画布.bind("<ButtonRelease-1>", 松开)

# ===== 状态行为 =====
def 抚摸():
    状态["心情"] = min(100, 状态["心情"] + 5)
    保存状态()
    显示气泡("❤ 好舒服，心情 +5")

def 喂食():
    if time.time() - 状态["最后喂食"] < 5:
        显示气泡("刚吃过啦，歇会儿")
        return
    状态["饥饿"] = min(100, 状态["饥饿"] + 30)
    状态["最后喂食"] = time.time()
    保存状态()
    显示气泡("🍗 吃得好饱，饥饿 +30")

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
    输入窗.configure(bg="#ffffff")
    tk.Label(输入窗, text="几分钟后提醒？", font=("Microsoft YaHei", 10), bg="#ffffff", padx=8, pady=4).pack()
    输入框 = tk.Entry(输入窗, font=("Microsoft YaHei", 11), width=12, relief="flat")
    输入框.pack(padx=8, pady=4)
    输入框.focus_set()
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 70
    y = 窗口.winfo_y() - 90
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

def 设速率(毫秒):
    global 帧间隔
    帧间隔 = int(float(毫秒))
    设置["速率"] = 帧间隔
    保存设置()

# ===== 自由移动（平滑插值）=====
移动目标x = None
移动目标y = None

def 切换自由移动():
    设置["自由移动"] = not 设置["自由移动"]
    保存设置()
    if 设置["自由移动"]:
        规划移动()

def 规划移动():
    global 移动目标x, 移动目标y
    if not 设置["自由移动"]:
        return
    屏宽 = 窗口.winfo_screenwidth()
    屏高 = 窗口.winfo_screenheight()
    移动目标x = 窗口.winfo_x() + random.randint(-150, 150)
    移动目标y = 窗口.winfo_y() + random.randint(-150, 150)
    移动目标x = max(0, min(移动目标x, 屏宽 - 画布.winfo_width()))
    移动目标y = max(0, min(移动目标y, 屏高 - 画布.winfo_height()))
    平滑移动()

def 平滑移动():
    global 移动目标x, 移动目标y
    if 移动目标x is None or not 设置["自由移动"]:
        return
    步长 = int(设置.get("移动速度", 5))
    当前x, 当前y = 窗口.winfo_x(), 窗口.winfo_y()
    dx = 移动目标x - 当前x
    dy = 移动目标y - 当前y
    if abs(dx) <= 步长 and abs(dy) <= 步长:
        窗口.geometry("+%d+%d" % (移动目标x, 移动目标y))
        移动目标x = 移动目标y = None
        窗口.after(random.randint(2000, 6000), 规划移动)
        return
    新x = 当前x + (步长 if dx > 0 else -步长 if dx < 0 else 0)
    新y = 当前y + (步长 if dy > 0 else -步长 if dy < 0 else 0)
    窗口.geometry("+%d+%d" % (新x, 新y))
    窗口.after(30, 平滑移动)

# ===== DeepSeek =====
def 调用AI(问题):
    if not DeepSeek密钥:
        return "还没设置 DEEPSEEK_KEY 环境变量。"
    数据 = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": 问题}],
    }).encode("utf-8")
    请求 = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=数据,
        headers={"Authorization": "Bearer " + DeepSeek密钥, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(请求, timeout=60) as 响应:
            return json.loads(响应.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except Exception as e:
        return "出错了：" + str(e)

# ===== 文字聊天 =====
def 文字聊天():
    输入窗 = tk.Toplevel(窗口)
    输入窗.overrideredirect(True)
    输入窗.attributes("-topmost", True)
    输入窗.configure(bg="#ffffff")
    输入框 = tk.Entry(输入窗, font=("Microsoft YaHei", 11), width=30, relief="flat")
    输入框.pack(padx=8, pady=8)
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 130
    y = 窗口.winfo_y() - 50
    输入窗.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
    输入框.focus_set()

    def 提交(事件=None):
        问题 = 输入框.get().strip()
        输入窗.destroy()
        if not 问题:
            return
        显示气泡("思考中...", 30000)

        def 后台():
            回答 = 调用AI(问题)
            消息队列.put(lambda: 显示气泡(回答, 15000))

        threading.Thread(target=后台, daemon=True).start()

    输入框.bind("<Return>", 提交)
    输入框.bind("<Escape>", lambda e: 输入窗.destroy())

# ===== 语音聊天 + 语音控制 =====
def 语音聊天():
    import voice
    import app_launcher
    显示气泡("正在听...（4 秒）")

    def 后台():
        文字 = voice.录音识别(4)
        if not 文字:
            消息队列.put(lambda: 显示气泡("没听清，再说一次"))
            return
        if "打开" in 文字:
            关键词 = 文字.replace("打开", "").strip()
            名 = app_launcher.启动软件(关键词)
            结果 = ("已打开 " + 名) if 名 else ("没找到软件：" + 关键词)
            消息队列.put(lambda: 显示气泡(结果, 5000))
            voice.说话(结果)  # 语音播报
        else:
            回答 = 调用AI(文字)
            voice.说话(回答)  # 只朗读，不显示文字

    threading.Thread(target=后台, daemon=True).start()

# ===== 语音唤醒 =====
唤醒停止 = threading.Event()
唤醒线程 = None

def 切换唤醒():
    设置["语音唤醒"] = not 设置["语音唤醒"]
    保存设置()
    if 设置["语音唤醒"]:
        开启唤醒()
    else:
        关闭唤醒()

def 开启唤醒():
    global 唤醒线程, 唤醒停止
    import voice
    唤醒停止 = threading.Event()
    唤醒线程 = threading.Thread(target=voice.唤醒监听, args=(唤醒回调, 唤醒停止), daemon=True)
    唤醒线程.start()
    显示气泡("已开启语音唤醒，说“嗨”呼叫我")

def 关闭唤醒():
    global 唤醒停止
    唤醒停止.set()

def 唤醒回调():
    消息队列.put(语音聊天)

# ===== 自绘菜单 =====
def 显示菜单():
    菜单窗 = tk.Toplevel(窗口)
    菜单窗.overrideredirect(True)
    菜单窗.attributes("-topmost", True)
    菜单窗.configure(bg="#2b2b2b")
    边框 = tk.Frame(菜单窗, bg="#2b2b2b")
    边框.pack(padx=1, pady=1)
    项 = [
        ("聊天", 文字聊天),
        ("语音聊天", 语音聊天),
        ("状态", 显示状态),
        ("喂食", 喂食),
        ("设定提醒", 设提醒),
        ("设置", 打开设置面板),
        ("语音唤醒", 切换唤醒),
        ("退出", 窗口.destroy),
    ]
    for 标签, 命令 in 项:
        def 点击(c=命令, w=菜单窗):
            w.destroy()
            c()
        b = tk.Button(边框, text=标签, command=点击, font=("Microsoft YaHei", 10),
                      bg="#2b2b2b", fg="#e0e0e0", activebackground="#3a3a3a",
                      activeforeground="#ffffff", relief="flat", width=14, anchor="w", padx=12, pady=5)
        b.pack(fill="x")
    x = 窗口.winfo_x()
    y = 窗口.winfo_y() + 画布.winfo_height()
    菜单窗.geometry("+%d+%d" % (x, y))

# ===== 设置面板（无级滑块）=====
def 打开设置面板():
    面板 = tk.Toplevel(窗口)
    面板.overrideredirect(True)
    面板.attributes("-topmost", True)
    面板.configure(bg="#2b2b2b")
    标题 = tk.Label(面板, text="设置", font=("Microsoft YaHei", 12, "bold"), bg="#2b2b2b", fg="#ffffff")
    标题.pack(pady=6)

    def 加滑块(标签, 最小值, 最大值, 初始, 命令):
        行 = tk.Frame(面板, bg="#2b2b2b")
        行.pack(fill="x", padx=12, pady=4)
        tk.Label(行, text=标签, font=("Microsoft YaHei", 10), bg="#2b2b2b", fg="#cccccc", width=8).pack(side="left")
        s = tk.Scale(行, from_=最小值, to=最大值, resolution=0.1, orient="horizontal",
                     bg="#2b2b2b", fg="#ffffff", troughcolor="#444444", highlightthickness=0,
                     length=140, command=lambda v: None)
        s.set(初始)
        s.bind("<ButtonRelease-1>", lambda e, sl=s, cmd=命令: cmd(sl.get()))
        s.pack(side="left")
        return s

    加滑块("大小", 0.3, 2.0, 设置["大小"], 设大小)
    加滑块("速率", 20, 150, 设置["速率"], 设速率)
    加滑块("移动速度", 1, 20, 设置["移动速度"], lambda v: (设置.__setitem__("移动速度", int(float(v))), 保存设置()))

    tk.Button(面板, text="关闭", command=面板.destroy, font=("Microsoft YaHei", 10),
              bg="#3a3a3a", fg="#ffffff", relief="flat", padx=20, pady=4).pack(pady=6)
    x = 窗口.winfo_x() + 画布.winfo_width() // 2 - 90
    y = 窗口.winfo_y() - 180
    面板.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

# ===== 右键 =====
def 右键(事件):
    显示菜单()

画布.bind("<Button-3>", 右键)

if os.environ.get("PET_TEST") == "1":
    窗口.after(3000, 窗口.destroy)

窗口.mainloop()
