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
