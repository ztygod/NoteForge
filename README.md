<div align="center">

<br />

# NoteForge

<h3>Turn a public course video into structured Markdown study notes.</h3>

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab)
![CLI](https://img.shields.io/badge/Interface-CLI-6366f1)
![Tests](https://img.shields.io/badge/Tests-217%20passing-22c55e)

**Bilibili subtitle collection, LLM-powered knowledge extraction, and traceable notes**

[Quick start](#quick-start) · [Configuration](#llm-configuration) · [Usage](#usage) · [Troubleshooting](#troubleshooting) · [Development](#development)

**English** · [简体中文](https://github.com/ztygod/NoteForge/blob/main/README.zh-CN.md)

</div>

---

> [!WARNING]
> NoteForge is still under active development and has many incomplete or
> unpolished areas. Use it with caution. The author assumes no responsibility
> for any loss or damage resulting from its use.

![NoteForge CLI example](https://raw.githubusercontent.com/ztygod/NoteForge/main/asserts/example.png)

---

## Why NoteForge

Long course videos are useful, but turning them into reviewable notes takes time.
NoteForge collects a video's available subtitles, identifies semantic sections,
extracts key concepts with an LLM, and writes a structured Markdown document with
source timestamps.

```text
Bilibili URL
    ↓
Subtitle discovery, selection, download, and normalization
    ↓
Transcript chunking and semantic analysis
    ↓
Knowledge-point extraction
    ↓
Structured Markdown notes with timestamps
```

NoteForge downloads subtitles only. It does not download the video or audio.

---

## Capabilities

| Capability | What it does |
| --- | --- |
| **Source inspection** | Normalizes a URL and shows video, subtitle, and transcript metadata |
| **Subtitle selection** | Prefers a requested language, then supported Chinese and English tracks |
| **LLM analysis** | Supports OpenAI, Anthropic, and local Ollama models |
| **Note generation** | Creates organized Markdown notes with concepts, explanations, and timestamps |
| **Multi-part videos** | Handles the `p` parameter in Bilibili multi-part video URLs |

> Current scope: end-to-end note generation supports standard Bilibili video URLs
> with an available VTT or SRT subtitle track.

---

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Network access to Bilibili and the selected LLM provider
- A supported subtitle track on the target video
- For restricted videos: a locally installed, signed-in browser

Ollama users also need a running [Ollama](https://ollama.com/) installation and a
local model that follows JSON-output instructions reliably.

---

## Quick start

### 1. Install the command

```bash
uv tool install noteforge-cli
```

Confirm the CLI is ready:

```bash
noteforge --version
noteforge --help
```

If your shell cannot find the command after installation, run
`uv tool update-shell`, restart the terminal, and try again.

### 2. Configure an LLM

Start the interactive setup:

```bash
noteforge configure
```

For the default local Ollama setup, accept `ollama`, then prepare the suggested
model:

```bash
ollama pull qwen2.5:7b
```

The wizard stores the settings in a local `.env` file with user-only permissions.
NoteForge loads this file automatically. The default setup expects Ollama at
`http://localhost:11434`; keep `ollama serve` running if your installation does
not start it automatically.

For OpenAI or Anthropic, choose the provider in the wizard. API-key input is
hidden. You may also copy and edit `.env.example`; see
[LLM configuration](#llm-configuration).

### 3. Inspect a video before generating

```bash
noteforge inspect \
  "https://www.bilibili.com/video/BVxxxxxxxxxx" \
  --cookies-from-browser chrome
```

Check that the JSON output contains a non-null `selected_subtitle` and
`transcript`, and that `segment_count` is greater than zero.

### 4. Generate notes

```bash
noteforge generate \
  "https://www.bilibili.com/video/BVxxxxxxxxxx" \
  --output output/note.md \
  --cookies-from-browser chrome
```

The completed note is written to `output/note.md`. Parent directories are created
automatically.

---

## LLM configuration

NoteForge reads configuration from a `.env` file in the current directory and
from process environment variables. Values explicitly exported in the shell take
precedence over `.env`.

Run the setup again whenever you want to change providers or models:

```bash
noteforge configure
```

When `generate` detects missing configuration in an interactive terminal, it
offers to start the same wizard automatically. In scripts and CI it exits with a
clear instruction instead of waiting for input.

| Variable | Required | Description |
| --- | --- | --- |
| `NOTEFORGE_LLM_PROVIDER` | Yes | `ollama`, `openai`, or `anthropic` |
| `NOTEFORGE_LLM_MODEL` | Yes | Provider-specific model identifier |
| `NOTEFORGE_LLM_API_KEY` | OpenAI/Anthropic | Provider API key; not needed by Ollama |
| `NOTEFORGE_LLM_BASE_URL` | No | Custom endpoint; defaults depend on the provider |
| `NOTEFORGE_LLM_TIMEOUT_SECONDS` | No | Request timeout in seconds; default: `60` |

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
NOTEFORGE_LLM_MODEL=<an-available-chat-completions-model>
NOTEFORGE_LLM_API_KEY=<your-api-key>
NOTEFORGE_LLM_TIMEOUT_SECONDS=120
```

The default endpoint is `https://api.openai.com/v1`. OpenAI-compatible services can
be used by setting `NOTEFORGE_LLM_BASE_URL`.

### Anthropic

```dotenv
NOTEFORGE_LLM_PROVIDER=anthropic
NOTEFORGE_LLM_MODEL=<an-available-anthropic-model>
NOTEFORGE_LLM_API_KEY=<your-api-key>
NOTEFORGE_LLM_TIMEOUT_SECONDS=120
```

The default endpoint is `https://api.anthropic.com/v1`.

Never commit `.env` or a real API key. `.env` is ignored by Git.

---

## Usage

### Inspect

Use `inspect` to validate collection and subtitle access without calling an LLM:

```bash
noteforge inspect VIDEO_URL [OPTIONS]
```

Useful options:

```text
--cookies-from-browser TEXT  Browser used for cookies: chrome, edge, firefox, safari
--subtitle-language TEXT     Preferred language, for example zh-Hans, zh-CN, or en
--subtitle-output-dir PATH   Subtitle cache root
```

To try a public video without browser cookies:

```bash
noteforge inspect VIDEO_URL --cookies-from-browser ""
```

### Generate

```bash
noteforge generate VIDEO_URL [OPTIONS]
```

Examples:

```bash
# Prefer Simplified Chinese subtitles
noteforge generate VIDEO_URL \
  --subtitle-language zh-Hans \
  --output output/course-note.md

# Generate notes for part 2 of a multi-part video
noteforge generate \
  "https://www.bilibili.com/video/BVxxxxxxxxxx?p=2" \
  --output output/part-2.md

# Do not read browser cookies
noteforge generate VIDEO_URL \
  --cookies-from-browser "" \
  --output output/note.md
```

Run `noteforge COMMAND --help` for the complete option reference.

---

## Troubleshooting

### `缺少配置：NOTEFORGE_LLM_PROVIDER`

Run the interactive configuration:

```bash
noteforge configure
```

### Browser-cookie errors

Use the name of a browser installed on this machine and make sure it has a signed-in
Bilibili session:

```bash
noteforge inspect VIDEO_URL --cookies-from-browser firefox
```

For a public video, retry without cookies:

```bash
noteforge inspect VIDEO_URL --cookies-from-browser ""
```

Close the browser temporarily if its cookie database is locked.

### HTTP 412 or platform risk control

Use cookies from a signed-in browser, avoid repeated rapid requests, and retry
later. Platform-side risk control cannot be eliminated by NoteForge.

### No supported subtitle

Confirm the video exposes a subtitle track in Bilibili, try a preferred language
with `--subtitle-language`, and inspect the `subtitle_tracks` output. NoteForge
currently parses VTT and SRT tracks; it does not transcribe audio.

### The LLM returns invalid JSON

Use a model with strong instruction-following and structured-output ability. For a
small local model, try a larger model or increase the timeout. The partial output is
not written as a completed note.

### Connection or timeout failures

Check the provider URL and API key, then increase:

```dotenv
NOTEFORGE_LLM_TIMEOUT_SECONDS=180
```

---

## Development

```bash
git clone https://github.com/ztygod/NoteForge.git
cd NoteForge
uv sync --group dev
uv run pytest -q
uv build
```

Release installation, upgrade, and removal:

```bash
uv tool install noteforge-cli
uv tool upgrade noteforge-cli
uv tool uninstall noteforge-cli
```

### Publishing a release

The `noteforge` name is already owned by another project on PyPI. This project is
therefore distributed as `noteforge-cli` while continuing to expose the
`noteforge` terminal command.

Before the first release, register a pending Trusted Publisher on PyPI with:

```text
PyPI project name: noteforge-cli
GitHub owner: ztygod
GitHub repository: NoteForge
Workflow: publish.yml
Environment: pypi
```

Create a protected `pypi` environment in the GitHub repository and require manual
approval. Then publish a version by updating the version and pushing a matching
tag:

```bash
uv version 0.1.0
git add pyproject.toml uv.lock
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main v0.1.0
```

The workflow builds and validates both distributions before publishing through
PyPI Trusted Publishing; no long-lived PyPI token is stored in GitHub.

Project structure:

```text
noteforge/
├── src/noteforge/
│   ├── cli/          # Typer commands
│   ├── collector/    # Source inspection and Bilibili collection
│   ├── subtitle/     # Subtitle selection, parsing, and normalization
│   ├── knowledge/    # Chunking, semantic analysis, and extraction
│   ├── llm/          # OpenAI, Anthropic, and Ollama adapters
│   ├── document/     # Learning-document construction
│   ├── renderer/     # Markdown rendering and writing
│   └── core/         # End-to-end pipeline
├── tests/
├── .github/workflows/publish.yml
├── .env.example
├── pyproject.toml
└── uv.lock
```

---

<div align="center">

**From a long video to notes you can actually review.**

</div>
