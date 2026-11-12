"""把 frame0_抠图.png 转成多尺寸 Windows 图标 pet.ico"""
from PIL import Image
import os

基目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
源 = os.path.join(基目录, "frame0_抠图.png")
目标 = os.path.join(基目录, "pet.ico")

img = Image.open(源).convert("RGBA")
img.save(目标, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("已生成:", 目标)
