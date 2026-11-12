"""语音模块：edge-tts 晓伊合成 + funasr 识别"""
import os
import re
import sys
import json
import time
import queue
import uuid
import asyncio
import tempfile
import threading
import numpy as np
import sounddevice as sd
import edge_tts

# funasr 模型缓存放英文路径（避免中文路径问题）
os.environ.setdefault("MODELSCOPE_CACHE", r"D:\pet-funasr-models")
# 限制数学库线程数：默认吃满所有核，识别时会把 Tk 界面卡住
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

音色 = "zh-CN-XiaoxiaoNeural"  # 晓晓，温柔知性，更接近蝶的声音
基目录 = os.path.dirname(os.path.abspath(__file__))
语音包目录 = os.path.join(基目录, "voice_pack")  # 放入蝶的语音包后自动匹配播放

# ===== 语音包（蝶的原声，优先于 TTS）=====
def 找语音包(文字):
    """在 voice_pack 里找与文字匹配的现成语音（按最长公共片段匹配）"""
    if not os.path.isdir(语音包目录):
        return None
    去噪 = lambda s: re.sub(r"[，。！？、,.!?~～\s啊呀呢嘛吧哦哈啦]", "", s)
    文字归一 = 去噪(文字)
    if len(文字归一) < 2:
        return None
    最佳 = None
    最佳分 = 0
    精确 = None
    for f in os.listdir(语音包目录):
        if not f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
            continue
        名 = re.sub(r"^\d+_", "", os.path.splitext(f)[0])  # 去掉 "15_" 序号前缀
        for 前缀 in ("三角洲行动-", "三角洲行动", "蝶-", "蝶"):
            if 名.startswith(前缀):
                名 = 名[len(前缀):]
        名归一 = 去噪(名)
        if 名归一 == 文字归一:
            精确 = os.path.join(语音包目录, f)
        # 找最长公共片段（至少 3 字才算匹配）
        分 = 0
        for 长度 in range(min(len(文字归一), 8), 2, -1):
            if any(文字归一[i:i + 长度] in 名归一 for i in range(len(文字归一) - 长度 + 1)):
                分 = 长度
                break
        if 分 > 最佳分:
            最佳分 = 分
            最佳 = os.path.join(语音包目录, f)
    return 精确 or (最佳 if 最佳分 >= 3 else None)

# ===== 播放（全局串行，避免 SDL 并发崩溃）=====
播放锁 = threading.Lock()
停止标志 = False


def 停止播放():
    """立即停掉当前播放（挂断时用）"""
    global 停止标志
    停止标志 = True
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def 播放音频(路径, 可打断=False, 阈值=1200):
    """播放音频。可打断=True 时用户一说话就停。返回 True 表示被打断。
    全局加锁串行播放：pygame.mixer 非线程安全，并发 init/load/quit 会挂死或崩溃。"""
    global 停止标志
    import pygame
    with 播放锁:
        停止标志 = False
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.set_volume(0.5 if 可打断 else 1.0)
        pygame.mixer.music.load(路径)
        pygame.mixer.music.play()
        开始 = time.time()
        流 = None
        if 可打断:
            try:
                流 = sd.InputStream(samplerate=16000, blocksize=800, dtype="int16", channels=1)
                流.start()
            except Exception:
                流 = None
        try:
            while pygame.mixer.music.get_busy() and not 停止标志:
                if 流 is not None and time.time() - 开始 > 0.4:  # 跳过开播瞬间的自拾取
                    try:
                        块, _ = 流.read(800)
                        if int(np.abs(块).max()) > 阈值:
                            pygame.mixer.music.stop()
                            return True
                    except Exception:
                        流 = None
                pygame.time.wait(50)
        finally:
            if 流 is not None:
                try:
                    流.close()
                except Exception:
                    pass
    return False

# ===== 语音合成（edge-tts 兜底）=====
def 清洗文本(文字):
    """去掉 TTS 会念出来的符号：markdown、括号、emoji、奇怪标点"""
    文字 = re.sub(r"[*#`_~～—>\[\]【】（）()<>|\\]", "", 文字)
    文字 = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", 文字)
    文字 = re.sub(r"[：:；;、]", "，", 文字)
    文字 = re.sub(r"\s+", " ", 文字)
    return 文字.strip()

def 说话(文字, 完成回调=None, 等待=False):
    """说一句话。等待=True 时阻塞到播完（通话循环里用，避免录音和播放重叠）"""
    文字 = 清洗文本(文字)
    if not 文字:
        if 完成回调:
            完成回调()
        return
    音频 = 找语音包(文字)  # 有蝶的原声就优先用

    def 播():
        try:
            播放音频(音频 or 合成(文字))
        except Exception as e:
            print("播放失败:", e)
        finally:
            if 完成回调:
                完成回调()

    if 等待:
        播()
    else:
        threading.Thread(target=播, daemon=True).start()


def 合成(文字):
    """edge-tts 生成 mp3，返回路径"""
    mp3 = os.path.join(tempfile.gettempdir(), "pet_tts_%s.mp3" % uuid.uuid4().hex)
    asyncio.run(edge_tts.Communicate(文字, 音色).save(mp3))
    return mp3 if os.path.exists(mp3) else None

# ===== 可打断的语音合成 =====
def 说话可打断(文字):
    """播放语音（优先蝶的原声），用户一说话就停。返回 True 表示被打断"""
    文字 = 清洗文本(文字)
    if not 文字:
        return False
    try:
        音频 = 找语音包(文字) or 合成(文字)
    except Exception as e:
        print("TTS 失败:", e)
        return False
    if not 音频 or not os.path.exists(音频):
        print("音频未生成:", 音频)
        return False
    return 播放音频(音频, 可打断=True)

# ===== 语音识别（funasr，懒加载）=====
识别模型 = None

def 获取模型():
    global 识别模型
    if 识别模型 is None:
        try:
            import torch
            # 留一半 CPU 给界面，否则识别时动画/输入会明显卡顿
            torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4) // 2)))
            from funasr import AutoModel
            识别模型 = AutoModel(model="paraformer-zh")
        except Exception as e:
            raise RuntimeError(
                "语音引擎加载失败：%s —— 若是 DLL 错误，装一下 VC++ 2015-2022 运行库"
                % str(e)[:160])
    return 识别模型

def 录音识别(秒=4):
    """录音 N 秒并识别成文字"""
    数据队列 = queue.Queue()

    def 回调(indata, frames, t, status):
        数据队列.put(indata.copy())

    采样率 = 16000
    片段列表 = []
    # InputStream 给 numpy 数组（RawInputStream 给 bytes，funasr 用不了）
    with sd.InputStream(samplerate=采样率, blocksize=8000, dtype="int16",
                        channels=1, callback=回调):
        开始 = time.time()
        while time.time() - 开始 < 秒:
            try:
                片段列表.append(数据队列.get(timeout=1))
            except queue.Empty:
                continue
    if not 片段列表:
        return ""
    音频 = np.concatenate(片段列表).flatten().astype(np.float32) / 32768.0
    return _识别(音频, 采样率)

def _识别(音频, 采样率):
    """存 WAV 后识别（funasr 的 numpy 输入会走 torchaudio 加载，文件路径稳定）"""
    import soundfile as sf
    wav = os.path.join(tempfile.gettempdir(), "pet_rec.wav")
    sf.write(wav, 音频, 采样率, subtype="PCM_16")
    model = 获取模型()
    结果 = model.generate(input=wav)
    文字 = 结果[0].get("text", "") if 结果 else ""
    return 文字.replace(" ", "")  # funasr 输出字间带空格，去掉才能匹配"你好/打开"

# ===== 对话录音（说完自动停，像打电话）=====
def 录音到静音(最长=20, 静音时长=0.9, 阈值=500):
    """录到说完（连续静音超时）为止，返回识别文字。
    需连续 3 块（0.3 秒）超阈值才算有人说话，滤掉噪声爆点和外放残留。"""
    采样率 = 16000
    数据 = []
    静音计数 = 0
    有声块 = 0
    有效 = False
    with sd.InputStream(samplerate=采样率, blocksize=1600, dtype="int16", channels=1) as 流:
        开始 = time.time()
        while time.time() - 开始 < 最长:
            块, _ = 流.read(1600)  # 0.1 秒一块
            数据.append(块.copy())
            幅度 = int(np.abs(块).max())
            if 幅度 > 阈值:
                有声块 += 1
                静音计数 = 0
                if 有声块 >= 3:
                    有效 = True
            else:
                静音计数 += 1
                if 有效 and 静音计数 > int(静音时长 * 10):
                    break
    if not 有效:
        return ""
    音频 = np.concatenate(数据).flatten().astype(np.float32) / 32768.0
    return _识别(音频, 采样率)

# ===== 唤醒监听 =====
def 唤醒监听(回调, 停止事件):
    """循环录音识别，听到唤醒词就回调（后台线程）"""
    while not 停止事件.is_set():
        try:
            文字 = 录音识别(2)
        except Exception as e:
            print("唤醒识别失败:", e)
            time.sleep(1)
            continue
        if 文字 and ("你好" in 文字 or "嗨" in 文字 or "siri" in 文字.lower()):
            回调()
            time.sleep(1)
        else:
            time.sleep(0.2)
