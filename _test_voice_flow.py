"""模拟语音通话一轮：录音识别 → 说话"""
import time
import voice

print("1. 模拟录音识别(2秒)...")
try:
    文字 = voice.录音识别(2)
    print("   识别结果:", repr(文字))
except Exception as e:
    import traceback
    traceback.print_exc()
    print("   录音识别失败:", e)

print("2. 测试说话（edge-tts）...")
try:
    voice.说话("语音测试一下")
    time.sleep(4)
    print("   说话完成")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("   说话失败:", e)

print("3. 测试可打断说话...")
try:
    voice.说话可打断("能打断的语音测试")
    print("   可打断完成")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("   可打断失败:", e)

print("全部完成")
