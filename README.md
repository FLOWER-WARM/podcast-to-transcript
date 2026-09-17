# podcast-to-transcript 🎙️→📝

小宇宙播客单集链接 → 本地转写 → 结构化学习笔记，全程自动化、音频不出本机。

一个面向 AI CLI 助手（WorkBuddy / Claude Code 等）的**用户级 Skill**。安装后，把小宇宙单集链接发给助手并说「转文稿」，即可自动产出三件套：

| 产出 | 说明 |
|---|---|
| **raw 原稿** | 带时间戳的逐字转写底稿 |
| **整理版文稿** | 同音字纠错后的可读文稿 |
| **结构化笔记** | 按主题分块 + 口诀保留 + 易错点清单 |

## 特点

- **全程本地转写**：faster-whisper（CPU int8）+ av 自带解码，无需 ffmpeg，音频不上传任何第三方
- **一条命令起步**：发链接即触发，助手按 SKILL.md 全流程执行
- **踩坑即插即用**：内置 Windows HF symlink 损坏规避、hf-mirror 镜像、耗时预估公式（音频时长 × 1.17）
- **笔记有模板**：主题分块表格、主播口诀保留、时间戳贯穿方便回听

## 安装

### 1. 复制技能

```bash
# Windows
git clone https://github.com/<你的用户名>/podcast-to-transcript.git
xcopy /E /I podcast-to-transcript "%USERPROFILE%\.workbuddy\skills\podcast-to-transcript"

# macOS / Linux
git clone https://github.com/<你的用户名>/podcast-to-transcript.git
cp -r podcast-to-transcript ~/.workbuddy/skills/
```

### 2. 装依赖（建议独立 venv）

```bash
python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
```

仅依赖 `faster-whisper`（自动带上 ctranslate2/av），**无需系统 ffmpeg**。

### 3. 首次运行

首次转写会从 hf-mirror.com（HuggingFace 国内镜像）下载模型权重（small 约 483MB），之后秒加载。

## 使用

把小宇宙单集链接发给装了本技能的助手：

> `https://www.xiaoyuzhoufm.com/episode/xxxx` 转文稿

可选参数（在 SKILL.md 中说明）：
- 快速模式：`--beam 1`（约省一半时间，错字略多）
- 精准模式：`--model medium`（更准，CPU 上约慢一倍）

## 文件结构

```
podcast-to-transcript/
├── SKILL.md            # 技能说明：流程、参数、踩坑记录（助手读取执行）
├── requirements.txt    # Python 依赖
├── README.md
├── LICENSE
└── scripts/
    ├── fetch_episode.py    # 解析小宇宙单集页 → 元数据 + 音频直链
    └── transcribe.py       # faster-whisper 本地转写（CPU int8）
```

## 耗时参考

| 配置 | 42 分钟音频 |
|---|---|
| CPU int8 + beam5 | 约 50 分钟 |
| CPU int8 + beam1 | 约 25 分钟 |
| NVIDIA CUDA | 5–10 分钟 |

## 隐私与版权

- 转写**全程本地**，网络请求仅两处：抓取小宇宙公开单集页、下载音频直链
- 模型权重从 hf-mirror.com 下载（数据文件，不执行远程代码）；可自行改官方源
- 播客音频有版权，转写仅供个人学习，请勿商用或传播

## License

[MIT](LICENSE)
