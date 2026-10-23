"""直接用 frame0_抠图.png 的原始 alpha，套用到所有帧（不羽化）"""
from PIL import Image
import numpy as np
import os

基目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIF = r"C:\Users\PP\Desktop\照片\新建文件夹 (2)\oUPRVEMdHyAAA5iBBIQIqijXCzYpAarsDplAi.gif"
遮罩图 = os.path.join(基目录, "frame0_抠图.png")
OUT = os.path.join(基目录, "frames")

# 原始 alpha（保留用户抠图的边缘，含半透明抗锯齿）
alpha = np.array(Image.open(遮罩图).convert("RGBA").split()[3])
print("alpha 非零占比: %.1f%%" % (100 * (alpha > 0).sum() / alpha.size))

os.makedirs(OUT, exist_ok=True)
im = Image.open(GIF)
n = getattr(im, "n_frames", 1)

for i in range(n):
    im.seek(i)
    rgb = np.array(im.convert("RGB"))
    if rgb.shape[:2] != alpha.shape:
        raise SystemExit("尺寸不一致: 帧 %s vs 遮罩 %s" % (rgb.shape[:2], alpha.shape))
    out = np.dstack([rgb, alpha])
    Image.fromarray(out).save(os.path.join(OUT, "frame_%03d.png" % i))
    if (i + 1) % 20 == 0:
        print("  %d/%d" % (i + 1, n))

print("完成:", OUT)
