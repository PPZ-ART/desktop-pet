"""创建桌面快捷方式"""
import os
import win32com.client

def 创建桌面快捷方式(exe路径, 名称="桌面宠物"):
    桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
    lnk = os.path.join(桌面, 名称 + ".lnk")
    shell = win32com.client.Dispatch("WScript.Shell")
    快捷 = shell.CreateShortCut(lnk)
    快捷.Targetpath = exe路径
    快捷.WorkingDirectory = os.path.dirname(exe路径)
    快捷.IconLocation = exe路径
    快捷.save()
    return lnk

if __name__ == "__main__":
    exe = r"D:\py练习\desktop-pet\dist\DesktopPet\DesktopPet.exe"
    if os.path.exists(exe):
        lnk = 创建桌面快捷方式(exe)
        print("已创建快捷方式:", lnk)
    else:
        print("找不到 exe:", exe)
