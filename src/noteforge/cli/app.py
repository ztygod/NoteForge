"""NoteForge 命令行入口。"""

import asyncio
from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import sys

import typer

from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.config import LLMSettings, read_dotenv, write_llm_dotenv
from noteforge.core import NoteGenerationPipeline
from noteforge.exceptions import (
    CollectionError,
    LLMConfigurationError,
    NoteForgeError,
    SubtitleError,
)
from noteforge.llm import create_llm_client


app = typer.Typer(
    help="根据公开课视频生成结构化学习笔记。",
    no_args_is_help=True,
)

_SUBTITLE_PREVIEW_LIMIT = 5
_PROVIDER_DEFAULTS = {
    "ollama": ("qwen2.5:7b", "http://localhost:11434"),
    "openai": ("", "https://api.openai.com/v1"),
    "anthropic": ("", "https://api.anthropic.com/v1"),
}


def _subtitle_debug_output(
    collection: VideoCollectionResult,
) -> dict[str, object]:
    selected = collection.selected_subtitle
    transcript = collection.transcript
    return {
        "available_track_count": len(collection.subtitle_tracks),
        "subtitle_tracks": [
            asdict(track)
            for track in collection.subtitle_tracks
        ],
        "selected_subtitle": asdict(selected) if selected else None,
        "transcript": (
            {
                "language": transcript.language,
                "source": transcript.source,
                "segment_count": len(transcript.segments),
                "preview_limit": _SUBTITLE_PREVIEW_LIMIT,
                "preview": [
                    asdict(segment)
                    for segment in transcript.segments[
                        :_SUBTITLE_PREVIEW_LIMIT
                    ]
                ],
            }
            if transcript
            else None
        ),
    }


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version("noteforge"))
        raise typer.Exit()


def _prompt_provider(default: str = "ollama") -> str:
    while True:
        provider = typer.prompt(
            "LLM 服务商（ollama/openai/anthropic）",
            default=default,
        ).strip().lower()
        if provider in _PROVIDER_DEFAULTS:
            return provider
        typer.secho(
            "请输入 ollama、openai 或 anthropic。",
            fg=typer.colors.YELLOW,
            err=True,
        )


def _run_configuration_wizard(path: Path = Path(".env")) -> LLMSettings:
    """交互收集并保存 LLM 配置。"""

    existing = read_dotenv(path)
    existing_provider = existing.get(
        "NOTEFORGE_LLM_PROVIDER", "ollama"
    ).strip().lower()
    if existing_provider not in _PROVIDER_DEFAULTS:
        existing_provider = "ollama"

    typer.echo("欢迎使用 NoteForge！先完成一次 LLM 配置。")
    provider = _prompt_provider(existing_provider)
    default_model, default_base_url = _PROVIDER_DEFAULTS[provider]
    model = typer.prompt(
        "模型名称",
        default=existing.get("NOTEFORGE_LLM_MODEL") or default_model or None,
    ).strip()
    while not model:
        typer.secho("模型名称不能为空。", fg=typer.colors.YELLOW, err=True)
        model = typer.prompt("模型名称").strip()

    api_key = ""
    if provider in {"openai", "anthropic"}:
        existing_key = existing.get("NOTEFORGE_LLM_API_KEY", "")
        if existing_key and typer.confirm("保留现有 API Key？", default=True):
            api_key = existing_key
        else:
            api_key = typer.prompt(
                "API Key",
                hide_input=True,
            ).strip()
            while not api_key:
                typer.secho(
                    "该服务商需要 API Key。",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                api_key = typer.prompt("API Key", hide_input=True).strip()

    base_url = typer.prompt(
        "接口地址",
        default=(
            existing.get("NOTEFORGE_LLM_BASE_URL")
            or default_base_url
        ),
    ).strip()
    timeout = typer.prompt(
        "请求超时（秒）",
        default=existing.get("NOTEFORGE_LLM_TIMEOUT_SECONDS", "120"),
    ).strip()

    values = {
        "NOTEFORGE_LLM_PROVIDER": provider,
        "NOTEFORGE_LLM_MODEL": model,
        "NOTEFORGE_LLM_BASE_URL": base_url,
        "NOTEFORGE_LLM_TIMEOUT_SECONDS": timeout,
    }
    if api_key:
        values["NOTEFORGE_LLM_API_KEY"] = api_key

    try:
        settings = LLMSettings.from_env(values)
    except ValueError as error:
        typer.secho(f"配置无效：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    written_path = write_llm_dotenv(values, path)
    typer.secho(
        f"配置已保存到 {written_path}（权限仅限当前用户）。",
        fg=typer.colors.GREEN,
    )
    return settings


def _create_configured_llm_client():
    try:
        return create_llm_client()
    except LLMConfigurationError as error:
        if not sys.stdin.isatty():
            raise LLMConfigurationError(
                f"{error}；请先运行 `noteforge configure`。"
            ) from error
        typer.secho(f"尚未完成 LLM 配置：{error}", fg=typer.colors.YELLOW)
        if not typer.confirm("现在开始配置？", default=True):
            raise LLMConfigurationError(
                "尚未配置 LLM；请先运行 `noteforge configure`。"
            ) from error
        settings = _run_configuration_wizard()
        return create_llm_client(settings)


@app.callback()
def cli(
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="显示 NoteForge 版本并退出。",
    ),
) -> None:
    """NoteForge 命令行接口。"""


@app.command()
def configure(
    path: Path = typer.Option(
        Path(".env"),
        "--path",
        help="保存 NoteForge 环境变量的 dotenv 文件。",
    ),
) -> None:
    """交互设置 LLM 环境变量，首次使用时建议先运行。"""

    _run_configuration_wizard(path)


@app.command()
def inspect(
    url: str = typer.Argument(..., help="需要检查的公开课视频链接。"),
    cookies_from_browser: str = typer.Option(
        "chrome",  # 默认为谷歌浏览器
        "--cookies-from-browser",
        help="从指定浏览器读取 Cookie，例如 chrome、edge、firefox 或 safari。",
    ),
    subtitle_language: str | None = typer.Option(
        None,
        "--subtitle-language",
        help="优先选择的字幕语言，例如 zh-Hans、zh-CN 或 en。",
    ),
    subtitle_output_dir: Path = typer.Option(
        Path(".cache/noteforge/subtitles"),
        "--subtitle-output-dir",
        help="字幕缓存根目录。",
    ),
) -> None:
    """检查视频链接，采集视频信息并输出结构化调试数据。"""
    inspect_result = inspection.inspect_source(url)

    output = {
        "inspection": asdict(inspect_result),
        "video_collection_result": None,
        "subtitle": None,
    }

    # 目前只实现了B站视频信息采集，其他平台暂不支持远程采集。
    if (
        inspect_result.platform is inspection.InspectionPlatform.BILIBILI
        and inspect_result.normalized_source is not None
    ):
        try:
            collection = bilibili.collect_bilibili_video(
                source=inspect_result.normalized_source,
                cookies_from_browser=cookies_from_browser,
                subtitle_language=subtitle_language,
                subtitle_output_dir=subtitle_output_dir,
                page_number=inspect_result.page_number,
            )
        except (CollectionError, SubtitleError) as error:
            typer.secho(f"采集失败：{error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from error
        output["video_collection_result"] = asdict(collection.metadata)
        output["subtitle"] = _subtitle_debug_output(collection)

    # 简要摘要便于人类阅读，后面的 JSON 保留给脚本和调试工具消费。
    typer.echo(f"平台：{inspect_result.platform.value}")
    if inspect_result.source_id is not None:
        typer.echo(f"视频 ID：{inspect_result.source_id}")
    if inspect_result.page_number is not None:
        typer.echo(f"分 P：{inspect_result.page_number}")
    typer.echo("结构化数据：")
    typer.echo(json.dumps(output, ensure_ascii=False, indent=2))


@app.command()
def generate(
    source: str = typer.Argument(..., help="需要生成学习笔记的视频 URL。"),
    output: Path = typer.Option(
        Path("output/note.md"),
        "--output",
        "-o",
        help="生成的 Markdown 文件路径。",
    ),
    cookies_from_browser: str | None = typer.Option(
        "chrome",
        "--cookies-from-browser",
        help="从指定浏览器读取 Cookie；传入空字符串可禁用。",
    ),
    subtitle_language: str | None = typer.Option(
        None,
        "--subtitle-language",
        help="优先选择的字幕语言。",
    ),
    subtitle_output_dir: Path = typer.Option(
        Path(".cache/noteforge/subtitles"),
        "--subtitle-output-dir",
        help="字幕缓存根目录。",
    ),
) -> None:
    """从视频字幕生成 Markdown 学习笔记。"""

    try:
        client = _create_configured_llm_client()
        pipeline = NoteGenerationPipeline.from_llm_client(client)
        written_path = asyncio.run(
            pipeline.run(
                source,
                output,
                cookies_from_browser=cookies_from_browser or None,
                subtitle_language=subtitle_language,
                subtitle_output_dir=subtitle_output_dir,
            )
        )
    except NoteForgeError as error:
        typer.secho(f"生成失败：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"学习笔记已生成：{written_path}")


def main() -> None:
    """启动 NoteForge 命令行程序。"""
    app()
