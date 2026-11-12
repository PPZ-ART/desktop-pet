"""创建桌面快捷方式（用 pet.ico 作图标）"""
import os
import win32com.client

基目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def 创建桌面快捷方式(exe路径, 图标路径=None, 名称="桌面宠物"):
    桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
    lnk = os.path.join(桌面, 名称 + ".lnk")
    shell = win32com.client.Dispatch("WScript.Shell")
    快捷 = shell.CreateShortCut(lnk)
    快捷.Targetpath = exe路径
    快捷.WorkingDirectory = os.path.dirname(exe路径)
    快捷.IconLocation = 图标路径 if 图标路径 and os.path.exists(图标路径) else exe路径
    快捷.save()
    return lnk

if __name__ == "__main__":
    exe = r"D:\pet-dist9\DesktopPet\DesktopPet.exe"
    图标 = os.path.join(基目录, "pet.ico")
    if os.path.exists(exe):
        lnk = 创建桌面快捷方式(exe, 图标)
        print("已创建快捷方式:", lnk, "| 图标:", 图标 if os.path.exists(图标) else "exe 默认")
    else:
        print("找不到 exe:", exe)
