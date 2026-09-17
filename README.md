# podcast-to-transcript

把小宇宙播客单集转成文字稿的助手技能。给助手发一个小宇宙链接，它会抓取音频、用本地的 faster-whisper 转写，整理出一份带时间戳的文稿，再按内容类型整理成笔记。整个过程音频不出本机，不需要 ffmpeg。

这个技能最初是为了把公考常识类播客转成复习笔记做的，后来发现访谈、新闻评论这类内容也用得上，笔记结构会根据内容自动调整。

## 它能做什么

- 解析小宇宙单集页面，拿到标题、时长、音频地址（不提供文字稿的节目也能转）
- 本地转写，支持 m4a/mp3，不用装 ffmpeg
- 转写结果按说话内容分段，带时间戳，方便回听定位
- Whisper 中文输出会有不少同音字错误（比如"元谋人"变"原某人"），技能会按内容领域做纠正，再整理成笔记
- 笔记结构跟着内容走：知识讲解类整理成考点和易错点，访谈类整理成观点摘要和原话引用，新闻类整理成事实和时间线

## 安装

把仓库克隆下来，复制到助手的技能目录：

```bash
git clone https://github.com/FLOWER-WARM/podcast-to-transcript.git

# Windows，复制到
xcopy /E /I podcast-to-transcript "%USERPROFILE%\.workbuddy\skills\podcast-to-transcript"

# macOS / Linux
cp -r podcast-to-transcript ~/.workbuddy/skills/
```

装依赖，建议建个虚拟环境，别装到全局：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt           # macOS / Linux
```

依赖只有 faster-whisper 一个，首次转写会自动下载模型（small 版约 483MB，走国内镜像）。

## 使用

对装了这个技能的助手发一句：

```
https://www.xiaoyuzhoufm.com/episode/xxxx 转文稿
```

剩下的助手自己会做。转写速度参考：CPU 上跑 42 分钟的音频大约 50 分钟，`--beam 1` 能快一半但错字会多一点，有 N 卡的话改 CUDA 几分钟就完。

## 说明

- 转写完全在本地进行，联网只发生在抓取单集页面和下载音频这两步
- 模型从 hf-mirror.com 下载，只是数据文件；介意的话可以自己改官方源
- 播客内容有版权，转写仅供个人学习

## License

MIT
