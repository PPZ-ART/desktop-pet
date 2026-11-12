# 桌面宠物 · 莉娜（代号“蝶”）

> 跑在 Windows 桌面上的 AI 伴侣：157 帧手绘动画 + DeepSeek 大模型对话 + 本地语音识别 + 本机智能体用量监控，可一键打包成免安装 exe。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![License](https://img.shields.io/badge/License-MIT-green)

## 亮点

| 能力 | 说明 |
|---|---|
| **157 帧透明动画** | 无边框置顶窗口，`-transparentcolor` 抠圆角；支持拖拽、抚摸、喂食、甩尾惯性、贴边吸附、睡眠 |
| **DeepSeek 多轮对话** | 人设化 System Prompt（角色设定 500+ 字）；20 秒超时、本地代理自动探测、失败不污染上下文；密钥三级回退（环境变量 → agent_keys.json → settings.json） |
| **本地语音** | funasr paraformer 中文识别 + 蝶的原声语音包（53 段），支持语音聊天与连续通话（像打电话） |
| **本机智能体联动** | 扫描桌面 / 开始菜单快捷方式调度 WorkBuddy、ZCode；只读 SQLite 统计上下文占用与积分；一键派发任务 |
| **可交付** | PyInstaller onedir 打包 1.2G 免安装包，解决 torch / c10.dll 的 WinError 1114；带 `PET_TEST_*` 自动化验收钩子 |

详细功能表、实现位置与踩坑记录见下文。

---

Windows 桌面常驻宠物。157 帧 PNG 动画 + DeepSeek 多轮对话 + funasr 语音识别 + 蝶的原声语音包 + 软件开关控制 + 无级随机游走 + 本地智能体监控（ZCode / WorkBuddy 用量、积分、额度、派发）+ 陪伴行为（睡眠、自言自语、点击音效、甩尾惯性、贴边吸附、开机自启、余额挂件）。

- 角色：莉娜·范德梅尔（《三角洲行动》医疗干员，代号“蝶”），人设见 `main.py` 的 `系统提示`
- Python 3.12 / tkinter / Pillow / funasr / edge-tts / pygame / pywin32

---

## 1. 快速开始

```powershell
pip install -r requirements.txt
setx DEEPSEEK_KEY "sk-你的key"      # 新开终端生效
python main.py
```

首次语音识别会自动下载 funasr 模型到 `D:\pet-funasr-models`（约 1GB，`voice.py` 里 `MODELSCOPE_CACHE` 指定）。

## 2. 目录结构

```
desktop-pet/
├─ main.py                 主程序：窗口/动画/菜单/气泡/聊天/语音通话/移动/设置
├─ voice.py                语音：语音包匹配、edge-tts、funasr 识别、全局串行播放
├─ app_launcher.py         软件启动/关闭（开始菜单扫描 + 窗口标题匹配）
├─ agent_monitor.py        智能体监控：ZCode/WorkBuddy 用量聚合、额度窗口、剪贴板派发
├─ frames/                 157 帧 PNG（透明背景，frame0…frame156）
├─ voice_pack/             53 段蝶的原声 wav，文件名 = 台词（如 47_别担心.wav）
├─ aliases.json            软件别名表（"浏览器" → "Microsoft Edge"）
├─ apps.json               开始菜单扫描缓存（可删，会重新扫描）
├─ settings.json           运行配置：大小/速率(0-10)/自由移动/移动速度(1-20)/语音唤醒
├─ pet_state.json          心情、饥饿、最后喂食时间
├─ pet.ico                 快捷方式图标
├─ DesktopPet.spec         PyInstaller 打包配置（含 voice_pack 与各依赖 collect_all）
├─ frame0_原图.png         原始形象
├─ frame0_抠图.png         去背景版（图标来源）
└─ tools/
   ├─ extract_frames.py       从 GIF 抽帧 → frames/
   ├─ extract_voicepack.py    语音合集按静音切分 + funasr 自动识别命名 → voice_pack/
   ├─ make_icon.py            PNG → pet.ico
   └─ create_shortcut.py      生成桌面快捷方式（改 exe 路径后运行）
```

## 3. 功能与实现位置

| 功能 | 实现 | 位置 |
|---|---|---|
| 透明无边框窗口 + 置顶 | `overrideredirect` + `-transparentcolor "#010203"` | `main.py` 窗口段 |
| 帧动画 | `after(帧间隔)` 轮播 `帧列表` | `main.py` 动画段 |
| 左键拖动 / 单击抚摸 | `<Button-1>` / `<B1-Motion>` / `<ButtonRelease-1>` | `main.py` 拖动段 |
| 右键菜单 | Canvas 圆角 + 半透明 0.92 + ESC 关闭 + 单例防重复 | `main.py` 显示菜单 |
| 气泡 | Canvas 圆角，优先上方/下方，不遮挡宠物 | `main.py` 显示气泡 |
| 文字聊天 | 多轮上下文（保留 10 轮）+ 输入框常驻 | `main.py` 文字聊天 / 调用AI |
| 语音聊天（单次 4 秒） | `voice.录音识别(4)` → AI → 朗读 | `main.py` 语音聊天 |
| 语音通话（连续） | 录音到静音循环，可插话打断，说“挂断/退出/再见”结束 | `main.py` 语音通话 |
| 语音唤醒 | 循环「录 2 秒 + 识别」，命中“你好/嗨”触发 | `voice.py` 唤醒监听 |
| 打开/关闭软件 | 开始菜单扫描 + 别名 + 窗口标题 `WM_CLOSE`/taskkill | `app_launcher.py` |
| 自由移动 | 浮点航向随机游走，避让其他窗口，边界折返 | `main.py` 游走一步 |
| 状态养成 | 心情/饥饿，喂食 +30，随时间缓慢下降 | `main.py` 状态段 |
| 提醒 | 菜单输入分钟数 → 气泡 | `main.py` 设提醒 |
| 设置面板 | 大小 0.3-2.0、速率 0-10、移动速度 1-20 滑块 | `main.py` 打开设置面板 |
| 智能体用量/额度 | 菜单「智能体」面板；聊天/语音说"用量/额度/token"播报 | `agent_monitor.py` + `main.py` 智能体面板 |
| 平台余额 | 「配置智能体」填 API Key 后，面板显示 DeepSeek/智谱/阿里云余额 | `agent_monitor.py` 平台余额文本 |
| 调用本地智能体 | "调用智能体 + 任务"→任务进剪贴板并打开目标应用，自动粘贴发送 | `agent_monitor.py` 调用智能体 |
| 检索本地智能体 | 面板「检索本地」→ 列出桌面/开始菜单里的 AI 软件，多选加入派发目标 | `main.py` 打开本地智能体检索 |
| 自定义平台 | 「配置智能体」底部填平台名 → 新增密钥行，保存进 `agent_extra.json` | `main.py` 打开智能体配置 |
| 余额挂件 | 设置里开启，宠物下方常驻小条，60 秒刷新 WorkBuddy 积分/token + ZCode 用量 | `main.py` 刷新挂件 |
| 睡眠模式 | 23:00-7:00 动画降速到 400ms/帧（设置可关） | `main.py` 睡眠中 / 播放 |
| 点击音效 | 单击抚摸时播系统提示音（`winsound`，无需素材） | `main.py` 播音效 |
| 自言自语 | 闲置 8-15 分钟随机说一句台词（语音包原声优先） | `main.py` 自言自语循环 |
| 甩尾惯性 | 拖动松手按速度滑行并衰减，停下自动贴边（28px 内吸附） | `main.py` 甩出去 / 惯性步 |
| 开机自启 | 菜单「开机自启（开/关）」写 `HKCU\...\Run` | `main.py` 切换自启 |
| 智能体联动 | 每 20 秒比对 WorkBuddy token，涨了就冒泡提示“刚跑了 X token” | `agent_monitor.py` 活动提示 |
| 派发模式 | 面板「新对话」勾选：勾=Ctrl+N 开新会话，不勾=发到当前会话 | `main.py` 派发 |
| 挂件数据源 | 设置「挂件显示」可选 全部 / WorkBuddy / ZCode / DeepSeek | `main.py` 刷新挂件 |
| 互动音效 | 抚摸播蝶的原声「嗯嗯」、喂食播「真好」，无语音包时用合成叮声；同时原地蹦两下 | `main.py` 播音效 / 开心跳 |

### 智能体监控说明

- **用量来源**：ZCode 读 `~/.zcode/cli/db/db.sqlite` 的 `model_usage` 表（按智能体 `agent` 列 / `model_id` 聚合）；WorkBuddy 读 `~/.workbuddy/workbuddy.db` 的 `sessions` + `session_usage`（每会话已用/上下文窗口/积分）。两库均只读方式打开，与运行中的应用并发无冲突。
- **平台余额**：`agent_keys.json`（gitignore，不打包）保存密钥，菜单「配置智能体」填写，每平台独立增删行（Entry 单行不换行）。DeepSeek 走 `/user/balance`；智谱走 `/api/monitor/usage/quota/limit`（仅编码计划 key 有数据，普通 key 提示去控制台；**平台余额官方无公开接口**）；阿里云填 `AccessKeyID,AccessKeySecret` 走 BSS `QueryAccountBalance`+`QueryCashCoupons`（HMAC-SHA1 签名，纯标准库），填百炼 `sk-` key 则只登记（DashScope 无余额 API），卡券明细看 https://billing-cost.console.aliyun.com/coupons/coupon ；**高德官方没有余额/配额查询接口**，只登记 Key，用量看 https://console.amap.com/dev/flow/manage 。「剩余额度」按钮会打开所有已配置平台的官方页面（含上面两个地址）。
- **派发直发**：派发 = 复制剪贴板 → 打开目标应用 → 等窗口出现（最长 30s）→ 确认焦点在该窗口 → Ctrl+N 新对话 → Ctrl+V → Enter。焦点确认失败就不发键（防止打错地方），任务留在剪贴板。全程写 `agent_task.log`。
- **网络**：DeepSeek 在部分网络下直连超时（WinError 10060，curl 同样超时，是网络层问题）。代码已做兜底：直连失败后探测本机常见代理端口（7890/7897/10809/10808/1080/8080/8888）自动重试，也可用 `PET_PROXY` 指定（聊天与余额查询都覆盖）。超时 20 秒，失败不写入对话历史。
- **派发目标**：启动时后台扫描桌面快捷方式识别智能体（workbuddy/zcode/codex/deepseek/豆包/kimi/通义等关键词），WorkBuddy 排第一（用户常用）。面板打开时后台刷新缓存。
- **剩余额度**：Z.ai 套餐（5 小时窗口 + 每周窗口双重限流）没有公开查询 API，凭证又是加密存储的，所以面板展示的是**两个滚动窗口的已用量**（本地现算），精确剩余与上限走面板「剩余额度」按钮直达 `z.ai/manage-apikey/billing`。
- **调用智能体为什么是"剪贴板方案"**：ZCode CLI 0.17.0 的无头模式（`-p` / `-c` / `--resume`）实测都不加载已保存的模型选择，直接报 "Select a model before sending a message"；app-server 协议又缺宿主依赖起不了会话。所以派发 = 任务自动写入剪贴板 + 自动打开 ZCode 桌面端，用户 Ctrl+V 发送即可。
- **弹窗焦点与拖动**：所有 `overrideredirect` 弹窗都 `focus_force()` 后 ESC 才能生效；智能体面板和配置窗按住空白处可拖动。新加弹窗记得带上。

## 4. 语音链路（三层）

1. **语音包原声**：`voice_pack/` 里的蝶的台词，按文件名与待播文本匹配（忽略标点/语气词，最长公共片段 ≥3 字）。命中即播原声，秒回。
2. **edge-tts**：`zh-CN-XiaoxiaoNeural`（晓晓），未命中语音包时兜底。
3. **识别**：funasr `paraformer-zh`，16kHz 单声道。

识别流程：录音 → `soundfile` 写临时 WAV → `model.generate(input=wav)` → `text.replace(" ", "")`。

通话录音判定（`voice.录音到静音`）：
- 阈值 500，需**连续 3 块（0.3s）**超阈值才算“有人说话”，滤掉噪声爆点
- 连续静音 0.9s 视为说完，单轮最长 20s
- 无有效人声返回空串

## 5. 打包

```powershell
python -m PyInstaller --noconfirm --distpath D:/pet-dist4 --workpath D:/pet-build4 DesktopPet.spec
```

产物：`D:\pet-dist4\DesktopPet\DesktopPet.exe`（约 98MB，整目录约 1.2GB）

**注意**：不要用 `pyinstaller --name DesktopPet ...` 的方式（会尝试重写 `DesktopPet.spec`，本机报 `PermissionError`）。改 `DesktopPet.spec` 后跑 spec 方式最稳。

`DesktopPet.spec` 里 `datas` 已包含 `frames`、`aliases.json`、`pet.ico`、`voice_pack`；并 `collect_all` 了 funasr / torch / torchaudio / modelscope / sounddevice / edge_tts / soundfile / pygame。

快捷方式：

```powershell
python tools/create_shortcut.py   # 先改里面的 exe 路径
```

## 6. 踩过的坑（改代码前务必看）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 语音通话闪退 | `pygame.mixer` 非线程安全，两个线程同时 init/load/quit | 全局 `播放锁` 串行播放，**不要每次 `mixer.quit()`** |
| 2 | 识别永远“没听清” | funasr 输出字间带空格（`你 好`），关键词匹配失败 | 识别结果 `replace(" ", "")` |
| 3 | 识别空结果 | funasr 传 numpy 会走 torchaudio/ffmpeg 路径，不稳定 | 先写 WAV，再 `generate(input=wav)` |
| 4 | 宠物不动且横向抖动 | 旧直线步长算法：单轴过冲后反向修正 | 改浮点航向游走（速度/方向连续浮动） |
| 5 | 自由移动完全无反应 | 屏幕被窗口占满，避让每帧命中 → 永远 return | 连续 8 次躲不掉就 `避让失效`，照常走 |
| 6 | 没人说话莉娜却开口 | 开场提示语被麦克风拾回当用户输入 | 上一句记入回音过滤（difflib >0.5 丢弃）+ 播后静默 1.2s |
| 7 | 通话被自己打断/卡顿 | 插话检测阈值过低，TTS 外放自触发 | TTS 音量 0.5，跳过前 0.4s，阈值 1200 |
| 8 | 双路录音抢资源 | 唤醒与通话同时开 | 通话自动暂停唤醒，`切换唤醒` 在通话中直接拒绝 |
| 9 | exe 里语音模块加载失败 | PyInstaller 漏打包原生库（vosk 时期的 `libvosk.dll`） | 一律 `collect_all` |
| 10 | 打包报 PermissionError | 无法写 `DesktopPet.spec` | 用已有 spec 直接打包（见第 5 节） |
| 11 | 弹窗背景全透明、能看穿到桌面 | Tk 在 Windows 上 `-alpha` 与 `-transparentcolor` 同时设置会互相破坏（实测：两者同设 → 整个窗口透明） | **只保留 `-transparentcolor` 做圆角，不要设 `-alpha`**；要半透明就牺牲圆角，二选一 |
| 12 | 智能体面板点「刷新」UI 卡死 | `lambda: 填入(后台取全文())` 被投递到 UI 线程执行，网络请求在 UI 线程跑 | 后台线程取数据，只把 `填入(结果)` 投递回 UI |
| 13 | 智能体「没找到 ZCode/WorkBuddy」 | 原版把 `D:\智谱\ZCode\ZCode.exe` 写死 | 改为环境变量 → 桌面/开始菜单快捷方式自动探测（`找应用()`），路径变了也能找到 |
| 14 | 语音聊天卡顿 | torch 默认吃满所有 CPU 核；且语音聊天时唤醒监听还在并行推理 | `torch.set_num_threads(min(4, 核数/2))` + `OMP/MKL_NUM_THREADS=4`；语音聊天前暂停唤醒，结束恢复 |
| 15 | 宠物贴屏幕底部右键，菜单跑出屏幕 | 菜单固定 `y = 宠物底部`，没做边界判断 | 下方放不下就向上弹，右侧越界左移（`显示菜单` 末尾） |
| 16 | DeepSeek 失败后越聊越乱 | 失败时 user 消息已写进 `对话历史` | 改用临时历史，成功才提交 |
| 17 | 面板点「刷新」卡死 | 网络请求被投递到 UI 线程 | 后台取数，只把结果投递回 UI |
| 18 | exe 报 `WinError 1114 ... c10.dll` | 打包进 `_internal` 的 `msvcp140.dll` 是旧版，被 c10.dll 优先加载 | 启动时 `ctypes.CDLL` 预加载 System32 的运行库（同名 DLL 复用已加载版本），再 `add_dll_directory` 到 torch/lib |
| 19 | 文字聊天「啥也不会」 | 只读环境变量 `DEEPSEEK_KEY`，而从桌面启动的 exe 没有该变量 | 密钥改为三级回退：环境变量 → `agent_keys.json`（配置窗填的）→ `settings.json` |
| 20 | 检索不到 ChatGPT 等 Store 应用 | 它们是没有 TargetPath 的 UWP 快捷方式 | `扫快捷方式` 记录 `.lnk` 路径并用 `os.startfile(lnk)` 启动；再不行用「手动选exe」 |
| 11 | 无头调 ZCode 报 "Select a model" | CLI 无头模式不加载已存模型选择，app-server 无宿主 | 不硬绕无头，改剪贴板派发（见智能体监控说明） |
| 12 | 剪贴板写入静默失败 | win32 句柄是 64 位，`GlobalLock` 等不设 `argtypes` 传参会溢出 | 所有 clipboard/global 内存 API 显式声明 `argtypes/restype`；`OpenClipboard` 失败重试 |

## 7. 已知限制 / 建议后续

- funasr 首次加载 10–20 秒（CPU），之后常驻内存
- 唤醒是「录 2 秒 + 识别」轮询，CPU 占用偏高，可用 webrtcvad 或流式 paraformer 优化
- 语音包仅 53 句，AI 自由发挥仍靠 TTS，音色与蝶有差异
  - 曾尝试 GPT-SoVITS 本地克隆：CPU 每句约 36 秒，体验不可接受，已放弃
  - 想要真·蝶音色，建议接在线声音复刻 API（火山引擎/阿里云，有免费额度）
- 避让逻辑在窗口铺满全屏时会穿过窗口（无空位时的兜底）
- 打包体积 1.2GB 主要来自 torch
- `settings.json` 的「速率」0-10 映射：`毫秒 = 150 - 值 × 13`；旧版存毫秒会自动换算

## 8. 环境变量

| 变量 | 用途 |
|---|---|
| `DEEPSEEK_KEY` | DeepSeek API Key（缺失时聊天只回提示语）|
| `MODELSCOPE_CACHE` | 默认 `D:\pet-funasr-models`（`voice.py` 内 `setdefault`，可自行改）|
| `ZCODE_PATH` / `WORKBUDDY_PATH` | 手动指定 ZCode / WorkBuddy 的 exe 路径（默认自动从桌面+开始菜单快捷方式探测）|
| `PET_PROXY` | 手动指定查询余额用的本地代理，如 `http://127.0.0.1:7890`（默认自动探测常见端口）|
| `PET_TEST=1` | 启动 3 秒后自动退出，用于冒烟测试 |
| `PET_TEST_ASR=1` | 后台加载语音引擎，结果写 `asr_test.txt` 后退出（验收 DLL 是否修好）|
| `PET_TEST_CHAT=1` | 走一遍文字聊天完整链路（取密钥→DeepSeek），结果写 `chat_test.txt` 后退出 |
| `PET_UI_TEST=panel\|config\|settings\|menu` | 自动打开对应窗口并截图到 `_ui_test.png`，UI 调试用 |

## 9. 发布到 GitHub（下载即可用）

仓库必须包含：`frames/`（157 帧动画，**不能 gitignore**）、`voice_pack/`、`pet.ico`、`DesktopPet.spec`、`build.ps1`。
不包含：`settings.json`、`pet_state.json`、`apps.json`、`agent_keys.json`、`agent_extra.json`、`pet.log`（已在 `.gitignore`）。

```powershell
git init
git add .
git commit -m "莉娜桌宠 v1.0：语音对话 + 本地智能体监控 + 陪伴行为"
git remote add origin https://github.com/<你的账号>/<仓库名>.git
git branch -M main
git push -u origin main
```

发布 Release 附件（用户下载解压双击即用）：

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
# 产物 dist\DesktopPet\，把整个文件夹压成 zip 作为 Release 附件
Compress-Archive -Path dist\DesktopPet\* -DestinationPath DesktopPet-win64.zip -CompressionLevel Optimal
```

> 完整包约 1.2GB（torch 占大头），GitHub Release 单文件上限 2GB，可直传但下载慢。
> 想要小体积可发布源码包 + 让用户跑 `pip install -r requirements.txt` 后 `python main.py`。
> 首次运行语音会自动下载 funasr 模型（约 1GB）到 `D:\pet-funasr-models`，需联网一次。

GitHub Actions（可选，自动出包）：

```yaml
# .github/workflows/build.yml
name: build
on: [push, workflow_dispatch]
jobs:
  win:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt pyinstaller
      - run: python -m PyInstaller --noconfirm DesktopPet.spec
      - uses: actions/upload-artifact@v4
        with: { name: DesktopPet-win64, path: dist/DesktopPet }
```
