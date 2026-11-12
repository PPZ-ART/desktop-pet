"""从蝶的语音合集里切出常用语音，识别文字后放进 voice_pack"""
import os
import subprocess
import numpy as np
import soundfile as sf
import imageio_ffmpeg

基目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
源 = r"C:\Users\PP\Desktop\三角洲行动 - 蝶 - 语音合集(s8赛季)_爱给网_aigei_com.m4a"
wav全 = os.path.join(基目录, "_voice_full.wav")
输出目录 = os.path.join(基目录, "voice_pack")
os.makedirs(输出目录, exist_ok=True)

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
print("转码并截取 0-369 秒...")
subprocess.run([ffmpeg, "-y", "-i", 源, "-t", "369", "-ar", "16000", "-ac", "1", wav全],
               capture_output=True)

数据, sr = sf.read(wav全, dtype="float32")
print("时长: %.1f 秒" % (len(数据) / sr))

块 = int(0.05 * sr)
帧数 = len(数据) // 块
能量 = np.array([float(np.sqrt(np.mean(数据[i * 块:(i + 1) * 块] ** 2))) for i in range(帧数)])
阈值 = max(float(np.max(能量)) * 0.05, 0.003)
有声 = 能量 > 阈值

段列表 = []
开始 = None
静音计数 = 0
for i, 有 in enumerate(有声):
    if 有:
        if 开始 is None:
            开始 = i
        静音计数 = 0
    elif 开始 is not None:
        静音计数 += 1
        if 静音计数 > 7:  # 0.35 秒静音视为一句结束（更细）
            段列表.append((开始, i - 静音计数))
            开始 = None
if 开始 is not None:
    段列表.append((开始, 帧数))

print("检测到 %d 段" % len(段列表))

from funasr import AutoModel
模型 = AutoModel(model="paraformer-zh")

序号 = 0
for 起, 止 in 段列表:
    时长 = (止 - 起) * 0.05
    if 时长 < 0.35 or 时长 > 4:  # 只要短句（常用语）
        continue
    片段 = 数据[起 * 块:止 * 块]
    临时 = os.path.join(基目录, "_seg.wav")
    sf.write(临时, 片段, sr, subtype="PCM_16")
    结果 = 模型.generate(input=临时)
    文字 = (结果[0].get("text", "") if 结果 else "").replace(" ", "")
    if not 文字:
        continue
    安全名 = "".join(c for c in 文字 if c not in r'\/:*?"<>|')[:16]
    if not 安全名:
        continue
    序号 += 1
    输出 = os.path.join(输出目录, "%02d_%s.wav" % (序号, 安全名))
    sf.write(输出, 片段, sr, subtype="PCM_16")
    print("%02d %s" % (序号, 文字))

print("完成，共 %d 个语音" % 序号)
