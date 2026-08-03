<div align="center">

<br />

# NoteForge

<h3>将公开课视频转化为结构化 Markdown 学习笔记。</h3>

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab)
![CLI](https://img.shields.io/badge/Interface-CLI-6366f1)
![Tests](https://img.shields.io/badge/Tests-217%20passing-22c55e)

**B 站字幕采集、LLM 知识提取与可追溯学习笔记**

[快速开始](#快速开始) · [模型配置](#llm-配置) · [使用方法](#使用方法) · [常见问题](#常见问题) · [开发](#开发)

[English](https://github.com/ztygod/NoteForge/blob/main/README.md) · **简体中文**

</div>

---

> [!WARNING]
> NoteForge 目前仍处于开发阶段，存在许多不完善之处，请谨慎使用。
> 因使用本项目造成的任何损失，作者概不负责。

![NoteForge CLI 运行示例](https://raw.githubusercontent.com/ztygod/NoteForge/main/asserts/example.png)

---

## 为什么使用 NoteForge

公开课视频内容丰富，但手工整理成方便复习的笔记往往很耗时。NoteForge 会获取
视频字幕、识别语义章节、使用 LLM 提取关键知识点，并生成带来源时间戳的结构化
Markdown 文档。

```text
B 站视频链接
    ↓
发现、选择、下载并规范化字幕
    ↓
字幕分块与语义分析
    ↓
知识点提取
    ↓
生成带时间戳的结构化 Markdown 笔记
```

NoteForge 只下载字幕，不下载视频或音频。

---

## 功能

| 功能 | 说明 |
| --- | --- |
| **来源检查** | 规范化链接，展示视频、字幕及转录文本信息 |
| **字幕选择** | 优先选择指定语言，然后依次选择支持的中英文字幕 |
| **LLM 分析** | 支持 OpenAI、Anthropic 和本地 Ollama 模型 |
| **笔记生成** | 生成包含概念、解释和来源时间戳的 Markdown 笔记 |
| **分 P 视频** | 支持 B 站视频链接中的 `p` 分 P 参数 |

> 当前范围：端到端笔记生成支持带有 VTT 或 SRT 字幕的标准 B 站视频链接。

---

## 环境要求

- Python 3.11 或更高版本
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- 能够访问 B 站和所选 LLM 服务
- 目标视频包含支持的字幕轨道
- 对于受限视频：本机已安装并登录浏览器

使用 Ollama 时，还需要安装并运行 [Ollama](https://ollama.com/)，且所选本地模型
需要能可靠遵循 JSON 输出指令。

---

## 快速开始

### 1. 安装命令

```bash
uv tool install noteforge-cli
```

确认 CLI 可以使用：

```bash
noteforge --version
noteforge --help
```

如果安装后终端找不到命令，请运行 `uv tool update-shell`，重启终端后再试。

### 2. 配置 LLM

启动交互式配置向导：

```bash
noteforge configure
```

如果使用默认的本地 Ollama，选择或接受 `ollama`，然后准备向导建议的模型：

```bash
ollama pull qwen2.5:7b
```

向导会把配置保存到本地 `.env`，文件权限仅限当前用户，NoteForge 会自动加载。
默认配置连接 `http://localhost:11434`。如果你的 Ollama 安装不会自动启动服务，
请保持 `ollama serve` 正在运行。

如需使用 OpenAI 或 Anthropic，在向导中选择对应服务商即可；API Key 输入不会
显示在屏幕上。也可以复制并编辑 `.env.example`，具体参考
[LLM 配置](#llm-配置)。

### 3. 生成前检查视频

```bash
noteforge inspect \
  "https://www.bilibili.com/video/BVxxxxxxxxxx" \
  --cookies-from-browser chrome
```

确认 JSON 输出中的 `selected_subtitle` 和 `transcript` 不为 `null`，并且
`segment_count` 大于零。

### 4. 生成笔记

```bash
noteforge generate \
  "https://www.bilibili.com/video/BVxxxxxxxxxx" \
  --output output/note.md \
  --cookies-from-browser chrome
```

生成结果位于 `output/note.md`，程序会自动创建不存在的父目录。

---

## LLM 配置

NoteForge 会读取当前目录的 `.env` 和进程环境变量；Shell 中显式导出的变量
优先级高于 `.env`。

需要更换服务商或模型时，可以再次运行：

```bash
noteforge configure
```

在交互式终端执行 `generate` 且配置缺失时，程序会主动询问是否立即启动同一个
向导。在脚本或 CI 等非交互环境中，程序会直接给出配置命令，不会等待输入。

| 环境变量 | 是否必填 | 说明 |
| --- | --- | --- |
| `NOTEFORGE_LLM_PROVIDER` | 是 | `ollama`、`openai` 或 `anthropic` |
| `NOTEFORGE_LLM_MODEL` | 是 | 对应服务商的模型标识 |
| `NOTEFORGE_LLM_API_KEY` | OpenAI/Anthropic 必填 | 服务商 API Key；Ollama 不需要 |
| `NOTEFORGE_LLM_BASE_URL` | 否 | 自定义接口地址；各服务商均有默认值 |
| `NOTEFORGE_LLM_TIMEOUT_SECONDS` | 否 | 请求超时时间，单位为秒；默认 `60` |

### Ollama

```dotenv
NOTEFORGE_LLM_PROVIDER=ollama
NOTEFORGE_LLM_MODEL=qwen2.5:7b
NOTEFORGE_LLM_BASE_URL=http://localhost:11434
NOTEFORGE_LLM_TIMEOUT_SECONDS=120
```

### OpenAI

```dotenv
NOTEFORGE_LLM_PROVIDER=openai
NOTEFORGE_LLM_MODEL=<可用的-chat-completions-模型>
NOTEFORGE_LLM_API_KEY=<你的-api-key>
NOTEFORGE_LLM_TIMEOUT_SECONDS=120
```

默认接口地址为 `https://api.openai.com/v1`。配置
`NOTEFORGE_LLM_BASE_URL` 后，也可以连接兼容 OpenAI Chat Completions 的服务。

### Anthropic

```dotenv
NOTEFORGE_LLM_PROVIDER=anthropic
NOTEFORGE_LLM_MODEL=<可用的-anthropic-模型>
NOTEFORGE_LLM_API_KEY=<你的-api-key>
NOTEFORGE_LLM_TIMEOUT_SECONDS=120
```

默认接口地址为 `https://api.anthropic.com/v1`。

不要提交 `.env` 或真实 API Key；Git 已忽略 `.env`。

---

## 使用方法

### 检查视频

`inspect` 不会调用 LLM，适合先确认视频和字幕是否能正常采集：

```bash
noteforge inspect 视频链接 [选项]
```

常用选项：

```text
--cookies-from-browser TEXT  读取 Cookie 的浏览器：chrome、edge、firefox、safari
--subtitle-language TEXT     优先字幕语言，例如 zh-Hans、zh-CN 或 en
--subtitle-output-dir PATH   字幕缓存根目录
```

如果公开视频不需要浏览器 Cookie：

```bash
noteforge inspect 视频链接 --cookies-from-browser ""
```

### 生成笔记

```bash
noteforge generate 视频链接 [选项]
```

示例：

```bash
# 优先选择简体中文字幕
noteforge generate 视频链接 \
  --subtitle-language zh-Hans \
  --output output/course-note.md

# 生成分 P 视频的第 2 P
noteforge generate \
  "https://www.bilibili.com/video/BVxxxxxxxxxx?p=2" \
  --output output/part-2.md

# 不读取浏览器 Cookie
noteforge generate 视频链接 \
  --cookies-from-browser "" \
  --output output/note.md
```

运行 `noteforge 命令 --help` 可以查看完整选项。

---

## 常见问题

### `缺少配置：NOTEFORGE_LLM_PROVIDER`

运行交互式配置：

```bash
noteforge configure
```

### 浏览器 Cookie 读取失败

指定本机已经安装且登录了 B 站的浏览器：

```bash
noteforge inspect 视频链接 --cookies-from-browser firefox
```

对于公开视频，可以尝试禁用 Cookie：

```bash
noteforge inspect 视频链接 --cookies-from-browser ""
```

如果浏览器 Cookie 数据库被锁定，可以暂时关闭浏览器后重试。

### HTTP 412 或平台风控

使用已登录浏览器的 Cookie，避免短时间内重复请求，并稍后重试。NoteForge 无法
完全消除视频平台自身的风控。

### 没有支持的字幕

确认 B 站页面存在字幕；使用 `--subtitle-language` 尝试指定语言，并检查
`inspect` 输出中的 `subtitle_tracks`。NoteForge 当前解析 VTT 和 SRT 字幕，
不会从音频自动转录。

### LLM 返回的 JSON 无效

请选择指令遵循和结构化输出能力更强的模型。本地小模型出现此问题时，可以更换
更大的模型或增加超时时间。程序不会把不完整结果写成一份已完成的笔记。

### 连接失败或超时

检查模型接口地址和 API Key，然后适当增大：

```dotenv
NOTEFORGE_LLM_TIMEOUT_SECONDS=180
```

---

## 开发

```bash
git clone https://github.com/ztygod/NoteForge.git
cd NoteForge
uv sync --group dev
uv run pytest -q
uv build
```

正式版本的安装、升级与卸载：

```bash
uv tool install noteforge-cli
uv tool upgrade noteforge-cli
uv tool uninstall noteforge-cli
```

### 发布新版本

由于 PyPI 上的 `noteforge` 包名已经被其他项目占用，本项目使用
`noteforge-cli` 作为发行包名，同时继续向用户提供 `noteforge` 终端命令。

第一次发布前，需要在 PyPI 注册 Pending Trusted Publisher：

```text
PyPI 项目名称：noteforge-cli
GitHub Owner：ztygod
GitHub 仓库：NoteForge
Workflow：publish.yml
Environment：pypi
```

然后在 GitHub 仓库中创建受保护的 `pypi` Environment，并启用人工审批。更新
版本号并推送对应标签即可发布：

```bash
uv version 0.1.0
git add pyproject.toml uv.lock
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main v0.1.0
```

工作流会先构建并检查 wheel 和源码包，再通过 PyPI Trusted Publishing 发布；
GitHub 中不需要保存长期 PyPI Token。

项目结构：

```text
noteforge/
├── src/noteforge/
│   ├── cli/          # Typer 命令
│   ├── collector/    # 来源检查与 B 站采集
│   ├── subtitle/     # 字幕选择、解析与规范化
│   ├── knowledge/    # 分块、语义分析与知识提取
│   ├── llm/          # OpenAI、Anthropic 和 Ollama 适配器
│   ├── document/     # 学习文档构建
│   ├── renderer/     # Markdown 渲染与写入
│   └── core/         # 端到端流水线
├── tests/
├── .github/workflows/publish.yml
├── .env.example
├── pyproject.toml
└── uv.lock
```

---

<div align="center">

**把一段长视频，变成真正方便复习的笔记。**

</div>
