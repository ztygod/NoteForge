"""generate 子命令。"""

import asyncio
from pathlib import Path

import typer

from noteforge.cli.commands.configure import load_configured_llm_settings
from noteforge.cli.renderer import PipelineRenderer
from noteforge.cli.ui import StatusUI
from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.config import LLMSettings, llm_api_format_label
from noteforge.core import NoteGenerationPipeline
from noteforge.exceptions import NoteForgeError, PipelineExecutionError
from noteforge.llm import create_llm_client


def _default_output(inspected: inspection.InspectionResult) -> Path:
    """根据稳定来源 ID 生成默认输出路径。"""

    name = inspected.source_id or "note"
    if inspected.page_number is not None and inspected.page_number > 1:
        name += f"_p{inspected.page_number}"
    return Path("output") / f"{name}.md"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "时长未知"
    total_minutes = round(seconds / 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def _subtitle_description(collection: VideoCollectionResult) -> str:
    track = collection.selected_subtitle
    transcript = collection.transcript
    if track is None or transcript is None:
        return "没有可用字幕"
    kind = "自动字幕" if track.is_automatic else "人工字幕"
    return (
        f"{track.language} · {kind} · "
        f"{len(transcript.segments):,} 个片段"
    )


def _run_preflight(
    ui: StatusUI,
    inspected: inspection.InspectionResult,
    *,
    cookies_from_browser: str | None,
    subtitle_language: str | None,
    subtitle_output_dir: Path,
) -> VideoCollectionResult:
    """在创建模型客户端前采集并验证视频字幕。"""

    if (
        inspected.platform is not inspection.InspectionPlatform.BILIBILI
        or inspected.normalized_source is None
    ):
        raise NoteForgeError("当前只支持标准 B 站视频 URL")

    with ui.running("检查输入", "正在获取视频和字幕信息..."):
        collection = bilibili.collect_bilibili_video(
            source=inspected.normalized_source,
            cookies_from_browser=cookies_from_browser,
            subtitle_language=subtitle_language,
            subtitle_output_dir=subtitle_output_dir,
            page_number=inspected.page_number,
        )
    ui.success(
        "视频信息",
        f"{collection.metadata.title} · "
        f"{_format_duration(collection.metadata.duration)}",
    )
    if collection.transcript is None:
        ui.failure("字幕", _subtitle_description(collection))
        raise NoteForgeError(
            "视频没有可供处理的 VTT 或 SRT 字幕；"
            "可先运行 `noteforge doctor <视频URL>` 检查访问权限。"
        )
    ui.success("字幕", _subtitle_description(collection))
    return collection


def _render_task(
    ui: StatusUI,
    source: str,
    output: Path,
    settings: LLMSettings,
) -> None:
    ui.title("NoteForge")
    ui.info("来源", source)
    ui.info("输出", str(output))
    ui.info(
        "模型",
        f"{llm_api_format_label(settings.provider)} / {settings.model}",
    )
    ui.section("检查输入")


def generate(
    source: str = typer.Argument(..., help="需要生成学习笔记的视频 URL。"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="生成的 Markdown 文件路径；默认根据视频 ID 命名。",
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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="显示阶段指标与耗时。"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="失败时保存中间数据并显示原始异常。"
    ),
    llm_concurrency: int = typer.Option(
        3,
        "--llm-concurrency",
        min=1,
        help="单个 LLM 阶段允许同时执行的最大批次数。",
    ),
) -> None:
    """从视频字幕生成 Markdown 学习笔记。"""

    ui = StatusUI()
    renderer: PipelineRenderer | None = None
    try:
        inspected = inspection.inspect_source(source)
        output_path = output if output is not None else _default_output(inspected)
        settings = load_configured_llm_settings()
        _render_task(ui, source, output_path, settings)
        collection = _run_preflight(
            ui,
            inspected,
            cookies_from_browser=cookies_from_browser or None,
            subtitle_language=subtitle_language,
            subtitle_output_dir=subtitle_output_dir,
        )

        renderer = PipelineRenderer(verbose=verbose, show_header=False)
        client = create_llm_client(settings)
        pipeline = NoteGenerationPipeline.from_llm_client(
            client, max_concurrency=llm_concurrency
        )
        if hasattr(pipeline, "set_event_handler"):
            pipeline.set_event_handler(renderer.handle)

        async def run_and_close() -> Path:
            try:
                return await pipeline.run(
                    source,
                    output_path,
                    cookies_from_browser=cookies_from_browser or None,
                    subtitle_language=subtitle_language,
                    subtitle_output_dir=subtitle_output_dir,
                    precollected=collection,
                    **({"debug_dir": Path(".noteforge/debug")} if debug else {}),
                )
            finally:
                await client.aclose()

        written_path = asyncio.run(run_and_close())
    except PipelineExecutionError as error:
        assert renderer is not None
        renderer.render_error(error, debug=debug)
        if debug:
            typer.echo("调试快照：.noteforge/debug/", err=True)
        raise typer.Exit(code=1) from error
    except NoteForgeError as error:
        ui.failure("生成失败", str(error))
        raise typer.Exit(code=1) from error
    typer.echo(f"学习笔记已生成：{written_path}")
