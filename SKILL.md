---
name: podcast-to-transcript
description: 小宇宙/播客链接转文字稿。当用户发来小宇宙(xiaoyuzhoufm.com)单集链接、要求"播客转文稿/转文字/播客笔记/提取播客内容"时使用。流程：解析单集页拿元数据和音频直链 -> 下载音频 -> faster-whisper 本地 CPU 转写 -> 同音字纠错并整理成结构化笔记。
---

# 小宇宙播客 → 文字稿

## 安装（新机器 / 分享给别人）

1. 把整个 `podcast-to-transcript/` 文件夹放到 `~/.workbuddy/skills/`（Windows: `C:\Users\<用户名>\.workbuddy\skills\`）
2. 准备 Python ≥3.10，建议建独立 venv 后安装依赖（不要全局安装）：
   ```bash
   python -m venv <venv路径>
   <venv>/Scripts/python.exe -m pip install -r ~/.workbuddy/skills/podcast-to-transcript/requirements.txt
   ```
   核心依赖只有 `faster-whisper`（会自动带上 ctranslate2/av 等）；`av` 自带音频解码，**无需系统 ffmpeg**
3. 首次转写会从 `hf-mirror.com`（HuggingFace 国内镜像）下载模型权重（small 约 483MB）。镜像用于加速获取模型数据文件，不执行任何远程代码；对源有顾虑可改用官方源或手动下载模型目录
4. Windows 未开「开发者模式」时 HuggingFace 缓存 symlink 会损坏——本技能脚本已内置规避逻辑（见踩坑1），无需额外设置

## 前置

- Python: 本机为 `C:\Users\lenovo\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- venv: `C:\Users\lenovo\.workbuddy\binaries\python\envs\default`（faster-whisper 未装时在 venv 内 `python.exe -m pip install faster-whisper`，勿全局安装）
- 无需系统 ffmpeg（faster-whisper 的 `av` 包自带解码，m4a/mp3 直接吃）
- 本技能脚本目录：`~/.workbuddy/skills/podcast-to-transcript/scripts/`（其他机器按安装节自行替换 venv 路径）

## 流程

### 1. 解析单集页
```bash
python ~/.workbuddy/skills/podcast-to-transcript/scripts/fetch_episode.py <url>
```
- 小宇宙是 Next.js SPA，数据全在 `<script id="__NEXT_DATA__">` 的 `props.pageProps.episode` 里，curl 可直接拿到（无需登录）
- 关注字段：`audio_url`(enclosure.url)、`has_shownotes`、`duration_sec`
- **有 shownotes 直接用**，跳过转写；无则继续
- 该播客 `ai_summarize_allowed=false` 时小宇宙无文字稿、AI 总结不可用
- RSS 查找：iTunes API `itunes.apple.com/search?media=podcast&term=<播客名>` → feedUrl；未收录即无公开 RSS

### 2. 下载音频
```bash
curl -sSL -o audio/ep.m4a "<audio_url>"
```
- `media.xyzcdn.net` 直链公开可下；**必须 `-L` 跟随重定向**

### 3. 转写
```bash
C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
  ~/.workbuddy/skills/podcast-to-transcript/scripts/transcribe.py audio/ep.m4a <out>.txt
```
- HF 必须走镜像：`HF_ENDPOINT=https://hf-mirror.com`（脚本已内置）
- 耗时预估：**音频时长 × 1.17**（small/int8/beam5）；`--beam 1` 约减半；`--model base` 再快一半但错字更多
- 转写是长任务，**必须 run_in_background**，并用文稿尾部时间戳对总时长估算剩余进度，主动向用户汇报

### 4. 后处理（转写完必做，别在读取阶段中断）
- Whisper small 中文输出**同音字错误密集**，需按主题领域纠错。人名/朝代/战役/制度等专有名词几乎全错，按领域知识系统替换（例：「磨耳朵→摩耳朵」「元谋人→原某人」「事半功倍→失败功倍」「石器时代→时期时代」「打制/磨制石器→打着/摩制时期」「孙鹤峰→贺峰/超哥贺峰」「禅让→善让」「商纣王→商主王」「牧野之战→木野之战」「澶渊之盟→蚕银之盟」「纳土归宋→纳特归宋」）
- 讲者口误处：整理版中按史实修正并标注（如「南稻北粟」说反、口误归朝），不要把口误当事实写进笔记
- **一次性完成读取+整理**：中断后需重读 raw 文稿续作；raw 文稿是唯一底稿，保留不删

### 5. 结构化笔记（先判内容类型，再选模板）
不同内容的笔记结构差异很大，**不要套固定模板**。转写完先读 raw 文稿的开头 10% 和各时间段抽样，判断类型，再选对应模板：

| 内容类型 | 判断特征 | 笔记结构 |
|---|---|---|
| **知识/课程讲解** | 单人主讲、成体系、有考点/概念/口诀 | 主题分块表格（对象×考点×记忆法）+ 时间轴 + **易错点清单**（含口误纠正） |
| **访谈/对谈** | 多人对话、有嘉宾、观点交锋 | 嘉宾背景 → 核心观点摘要（按话题分组，标说话人）→ 值得记录的原话引用（带时间戳）→ 分歧/争议点 |
| **新闻/时事评论** | 围绕近期事件、多信源 | 事实清单（时间/地点/人物/数据）→ 各方立场对比 → 时间线 → 待观察问题 |
| **技术/教程** | 讲操作、命令、代码 | 概念解释 → 步骤清单（可直接照做）→ 代码/命令块 → 常见坑 |
| **故事/叙事** | 讲经历、案情、历史故事 | 情节主线 → 人物关系 → 关键转折（带时间戳回听定位） |

**通用规则**（所有类型都遵守）：
- 时间戳贯穿保留，方便回听定位
- 专有名词纠错优先于文采，纠错处不标注
- 讲者口误按事实修正并在笔记末尾集中说明，不冒充原话
- 结尾给一段「一句话总结」：这期值得听的价值点
- 判断不了类型时，按知识类的主题分块结构走，把表格列名换成该内容的核心维度
- 交付永远是三件：raw 原稿、纠错整理版文稿、笔记，一起 present

## 踩坑记录（Windows）

1. **HF snapshot symlink 损坏**：Windows 未开开发者模式时，`~/.cache/huggingface/hub/.../snapshots/` 下文件全是 0 字节，报 `File model.bin is incomplete: failed to read a value of size 4 at position 0`。**blob 实体其实完好**（snapshots 旁 blobs/ 目录），把 blob 拷成正常文件即可，无需重新下载。
2. **耗时低估**：短句多的播客段数可达音频分钟数 ×30 以上，不要按"400-600 段"拍脑袋估时；用"音频时长 ×1.17"口径。
3. 训练数据截止限制不存在，但small模型对专有名词（人名/朝代/战役）错字率高，领域纠错不可省。
