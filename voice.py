"""语音模块：edge-tts 晓伊合成 + vosk 识别 + 唤醒监听"""
import os
import sys
import json
import time
import queue
import asyncio
import tempfile
import threading
import sounddevice as sd
import vosk
import edge_tts

# vosk 底层是 C++，无法打开中文路径，模型放在英文目录
if getattr(sys, "frozen", False):
    中文模型路径 = os.path.join(sys._MEIPASS, "vosk-model")
    英文模型路径 = os.path.join(sys._MEIPASS, "vosk-model-en")
else:
    中文模型路径 = r"D:\pet-vosk-model"
    英文模型路径 = r"D:\pet-vosk-model-en"  # 可选：放英文模型后自动用英文唤醒
音色 = "zh-CN-XiaoyiNeural"  # 晓伊，少萝音

# ===== 语音合成（edge-tts）=====
def 说话(文字, 完成回调=None):
    def 后台():
        try:
            mp3 = os.path.join(tempfile.gettempdir(), "pet_tts.mp3")
            通信 = edge_tts.Communicate(文字, 音色)
            asyncio.run(通信.save(mp3))
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(mp3)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            pygame.mixer.quit()
        except Exception as e:
            print("TTS 失败:", e)
        finally:
            if 完成回调:
                完成回调()
    threading.Thread(target=后台, daemon=True).start()

# ===== 语音识别 =====
中文模型 = vosk.Model(中文模型路径)

def 录音识别(秒=4, 模型=None):
    """录音 N 秒并识别成文字"""
    数据队列 = queue.Queue()

    def 回调(indata, frames, t, status):
        数据队列.put(bytes(indata))

    m = 模型 or 中文模型
    采样率 = 16000
    with sd.RawInputStream(samplerate=采样率, blocksize=8000, dtype="int16",
                           channels=1, callback=回调):
        识别器 = vosk.KaldiRecognizer(m, 采样率)
        开始 = time.time()
        while time.time() - 开始 < 秒:
            try:
                data = 数据队列.get(timeout=1)
            except queue.Empty:
                continue
            识别器.AcceptWaveform(data)
        return json.loads(识别器.FinalResult()).get("text", "")

# ===== 唤醒监听 =====
def 唤醒监听(回调, 停止事件):
    """持续监听唤醒词，识别到就调回调（后台线程）"""
    模型路径 = 英文模型路径 if os.path.isdir(英文模型路径) else 中文模型路径
    try:
        m = vosk.Model(模型路径)
    except Exception:
        return
    数据队列 = queue.Queue()

    def 音频回调(indata, frames, t, status):
        数据队列.put(bytes(indata))

    采样率 = 16000
    with sd.RawInputStream(samplerate=采样率, blocksize=4000, dtype="int16",
                           channels=1, callback=音频回调):
        识别器 = vosk.KaldiRecognizer(m, 采样率)
        while not 停止事件.is_set():
            try:
                data = 数据队列.get(timeout=1)
            except queue.Empty:
                continue
            if 识别器.AcceptWaveform(data):
                文字 = json.loads(识别器.Result()).get("text", "").lower()
                if "嗨" in 文字 or "siri" in 文字 or "hey" in 文字:
                    回调()
