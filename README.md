# 桌面宠物 AI 助手

常驻桌面的 GIF 动态宠物，支持 AI 聊天、语音、唤醒、状态养成、软件控制。

## 功能

- 157 帧 GIF 动画，透明背景、可拖动
- 文字聊天（DeepSeek）、语音聊天（vosk 识别 + edge-tts 晓伊音色朗读）
- 语音唤醒（说"嗨"）+ 语音打开本地软件（扫描开始菜单 + 别名匹配）
- 抚摸/喂食/心情值/饥饿值/定时提醒
- 自由移动（平滑游走）、大小/速率/移动速度无级调节
- 自绘深色菜单、设置面板滑块

## 运行方法

```bash
# 依赖
pip install -r requirements.txt

# 模型（vosk 中文小模型，放到 D:\pet-vosk-model）
# 从 modelscope: git clone https://www.modelscope.cn/shuai1618/vosk-model-small-cn.git

# 环境变量
set DEEPSEEK_KEY=你的Key

# 运行
python main.py
```

## 打包 exe

```bash
pyinstaller --noconsole --onedir --name DesktopPet \
  --add-data "frames;frames" \
  --add-data "aliases.json;." \
  --add-data "D:/pet-vosk-model;vosk-model" main.py
```

## 技术栈

Python 3.12 / tkinter / Pillow / vosk（语音识别）/ edge-tts（语音合成）/ DeepSeek API / pygame（音频播放）
