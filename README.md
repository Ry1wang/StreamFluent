# StreamFluent — 卡拉 OK 视频自动化管线

基于 **CrewAI** 多智能体框架的 Podcast 自动化工具：扫描音频 → 生成卡拉 OK 视频 → 上传 Bilibili，全流程一键完成。

底层引擎使用 **Faster-Whisper** 转录、**ASS 字幕**逐字高亮、**FFmpeg** 渲染，LLM 编排层使用 **DeepSeek**（OpenAI 兼容接口）驱动 CrewAI 智能体。

---

## 项目结构

```
StreamFluent/
├── main.py                   # 一键启动入口（CrewAI 管线）
├── .env                      # API 密钥配置（本地，勿提交）
├── .env.example              # 配置模板
│
├── crew/                     # CrewAI 编排层
│   ├── agents.py             # 3 个智能体定义（DeepSeek LLM）
│   ├── tasks.py              # 3 个顺序任务定义
│   └── tools/
│       ├── scan_tools.py     # ScanDirectoryTool
│       ├── karaoke_tools.py  # ProcessKaraokeTasksTool
│       └── upload_tools.py   # BilibiliUploadTool
│
├── karaoke_gen.py            # 引擎层：Whisper 转录 + ASS 生成 + FFmpeg 渲染
├── generate_images.py        # 引擎层：PIL 生成背景图 / 封面图
├── scan_tasks.py             # 引擎层：目录扫描 + 任务 JSON 构建
├── bili_upload.py            # 引擎层：Bilibili 上传（单个/批量）
└── batch_run_kgen.py         # 旧版批量入口（仍可独立使用）
```

---

## 快速开始

### 1. 安装依赖

**系统依赖：**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

**Python 依赖（Python 3.8+）：**
```bash
pip install -r requirements.txt
```

主要依赖：`crewai`, `langchain-openai`, `faster-whisper`, `SQLAlchemy`, `Pillow`, `bilibili-api-python`, `python-dotenv`

### 2. 配置环境变量

复制模板并填入 DeepSeek API 密钥：
```bash
cp .env.example .env
```

`.env` 内容：
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_API_BASE=https://api.deepseek.com
```

### 3. Bilibili 登录（首次使用）

```bash
python bili_upload.py --login
```
扫描终端中的二维码，凭证将保存到 `bili_sess.json`（请勿提交到版本控制）。

### 4. 运行管线

```bash
# 完整流程：扫描 → 生产 → 上传
python main.py --dir ../PodCast

# 仅扫描 + 生产，跳过上传
python main.py --dir ../PodCast --skip-upload

# 指定 tasks.json 输出路径
python main.py --dir ../PodCast --tasks my_tasks.json
```

---

## CrewAI 多智能体架构

管线由 3 个顺序执行的智能体组成，均由 **DeepSeek** 驱动：

```
[Scanner Agent] → tasks.json → [Producer Agent] → DB → [Publisher Agent] → Bilibili
```

| 智能体 | 工具 | 职责 |
|---|---|---|
| **Podcast Content Scanner** | `ScanDirectoryTool` | 递归扫描目录，匹配音频与封面，自动生成缺失图片，输出 `tasks.json` |
| **Karaoke Video Producer** | `ProcessKaraokeTasksTool` | Whisper 转录 → ASS 字幕生成 → FFmpeg 渲染 MP4 |
| **Bilibili Content Publisher** | `BilibiliUploadTool` | 批量上传视频，附带标题、标签、分区和封面图 |

---

## 引擎层（独立使用）

CrewAI 层只是编排，各引擎模块均可独立调用。

### 单曲生成

```bash
python karaoke_gen.py song.mp3 background.jpg
```

### 代码调用

```python
from karaoke_gen import KaraokeGenerator

gen = KaraokeGenerator()
gen.add_task("episode.mp3", "bg.jpg")
gen.process_pending_tasks()
```

### 单视频上传

```bash
python bili_upload.py --upload output/video.mp4 --title "我的视频" --cover cover.jpg
```

### 批量上传（无 CrewAI）

```bash
python bili_upload.py --batch tasks.json
```

---

## 输出文件

所有生成文件保存在 `output/` 目录，命名格式 `{stem}_{timestamp}`：

| 文件 | 说明 |
|---|---|
| `*.txt` | 纯文本转录稿 |
| `*.ass` | 卡拉 OK 字幕（ASS 格式，逐字高亮） |
| `*.mp4` | 最终合成视频（1080p，静态背景 + 音频 + 字幕） |

任务状态通过 SQLite（`karaoke_tasks.db`）追踪：`pending` → `processing` → `completed` / `failed`。

---

## 配置说明

| 项目 | 位置 | 说明 |
|---|---|---|
| LLM 模型 | `crew/agents.py` | 替换 `deepseek_llm` 可切换任意 OpenAI 兼容模型 |
| Whisper 模型大小 | `karaoke_gen.py` `Transcriber` | 默认 `base`，改为 `medium`/`large` 提升精度 |
| 字幕样式 | `karaoke_gen.py` `SubtitleGenerator` | 修改 `[V4+ Styles]` 中的字体、大小、颜色 |
| 字幕位置 | `karaoke_gen.py` | 调整 `\pos(960,680)` 参数 |
| Bilibili 分区 | `scan_tasks.py` | 默认 `tid=181`（知识区），按需修改 |

---

## 常见问题

**Q: `OMP: Error #15: Initializing libomp.dylib`**
A: 已内置 `KMP_DUPLICATE_LIB_OK=TRUE` 修复，无需额外操作。

**Q: 生成速度慢？**
A: 默认 CPU 推理。有 NVIDIA 显卡时，在 `karaoke_gen.py` 的 `Transcriber` 中设置 `device="cuda"`。

**Q: Bilibili 上传失败？**
A: 重新运行 `python bili_upload.py --login` 刷新凭证。
