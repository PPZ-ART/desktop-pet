"""软件启动模块：扫描开始菜单快捷方式，按关键词启动"""
import os
import glob
import json
import win32com.client

基目录 = os.path.dirname(os.path.abspath(__file__))
缓存文件 = os.path.join(基目录, "apps.json")

def 扫描软件():
    软件 = {}
    目录列表 = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    shell = win32com.client.Dispatch("WScript.Shell")
    for 目录 in 目录列表:
        for lnk in glob.glob(os.path.join(目录, "**", "*.lnk"), recursive=True):
            try:
                快捷 = shell.CreateShortCut(lnk)
                目标 = 快捷.Targetpath
                名称 = os.path.splitext(os.path.basename(lnk))[0]
                if 目标 and os.path.exists(目标) and 名称:
                    软件[名称] = 目标
            except Exception:
                continue
    return 软件

def 获取软件表():
    if os.path.exists(缓存文件):
        try:
            return json.load(open(缓存文件, encoding="utf-8"))
        except Exception:
            pass
    软件 = 扫描软件()
    json.dump(软件, open(缓存文件, "w", encoding="utf-8"), ensure_ascii=False)
    return 软件

def 启动软件(关键词):
    软件 = 获取软件表()
    关键词 = 关键词.lower().replace(" ", "")

    # 1. 别名表（英文软件的谐音/叫法）
    别名文件 = os.path.join(基目录, "aliases.json")
    别名表 = {}
    if os.path.exists(别名文件):
        try:
            别名表 = json.load(open(别名文件, encoding="utf-8"))
        except Exception:
            pass
    if 关键词 in 别名表:
        目标名 = 别名表[关键词]
        if 目标名 in 软件:
            os.startfile(软件[目标名])
            return 目标名

    # 2. 关键词包含匹配
    for 名称, 路径 in 软件.items():
        名 = 名称.lower().replace(" ", "")
        if 关键词 in 名 or 名 in 关键词:
            os.startfile(路径)
            return 名称
    return None

def _关窗口(关键词):
    """按窗口标题关闭：先 WM_CLOSE，0.6 秒没关就强杀进程"""
    import win32gui
    import win32process
    import win32con
    import subprocess
    import time

    关键词 = 关键词.lower().replace(" ", "")
    找到 = []

    def 回调(句柄, _):
        try:
            if not win32gui.IsWindowVisible(句柄):
                return
            标题 = win32gui.GetWindowText(句柄).lower().replace(" ", "")
            if 标题 and 关键词 in 标题:
                找到.append((句柄, win32gui.GetWindowText(句柄)))
        except Exception:
            return

    win32gui.EnumWindows(回调, None)
    if not 找到:
        return None

    句柄, 标题 = 找到[0]
    win32gui.PostMessage(句柄, win32con.WM_CLOSE, 0, 0)
    time.sleep(0.6)
    if not win32gui.IsWindow(句柄):
        return 标题
    try:
        _, pid = win32process.GetWindowThreadProcessId(句柄)
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    except Exception:
        pass
    return 标题

def 关闭软件(文字):
    """从整句话里提取软件名并关闭（比简单 replace 更可靠）"""
    软件 = 获取软件表()
    别名表 = {}
    别名文件 = os.path.join(基目录, "aliases.json")
    if os.path.exists(别名文件):
        try:
            别名表 = json.load(open(别名文件, encoding="utf-8"))
        except Exception:
            pass

    # 1. 别名优先（"浏览器" → "Microsoft Edge"）
    for 别名, 标准名 in 别名表.items():
        if 别名 in 文字:
            结果 = _关窗口(标准名)
            if 结果:
                return 结果
    # 2. 软件表名称出现在句子里
    for 名称 in 软件:
        if 名称 in 文字:
            结果 = _关窗口(名称)
            if 结果:
                return 结果
    # 3. 去指令词/后缀后，与软件名双向模糊匹配（"Edge浏览器"→"Edge"、"网易云"→"网易云音乐"）
    关键词 = 文字
    for k in ("关闭", "关掉", "关了", "帮我", "把", "一下", "吧", "谢谢", "请", "掉"):
        关键词 = 关键词.replace(k, "")
    for 后缀 in ("浏览器", "软件", "音乐", "客户端", "播放器"):
        关键词 = 关键词.replace(后缀, "")
    关键词 = 关键词.strip()
    if 关键词:
        for 名称 in 软件:
            if 关键词 in 名称 or 名称 in 关键词:
                结果 = _关窗口(名称)
                if 结果:
                    return 结果
        结果 = _关窗口(关键词)
        if 结果:
            return 结果
    return None
