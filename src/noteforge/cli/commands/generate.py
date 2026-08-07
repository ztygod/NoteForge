"""generate 子命令。"""

import asyncio
from pathlib import Path

import typer

from noteforge.cli.commands.configure import load_configured_llm_settings
from noteforge.cli.renderer import PipelineRenderer
from noteforge.cli.ui import StatusUI
from noteforge.collector import source as inspection
from noteforge.media.models import VideoResource
from noteforge.config import LLMSettings, llm_api_format_label
from noteforge.core import NoteGenerationPipeline
from noteforge.core.events import compose_event_handlers
from noteforge.exceptions import NoteForgeError, PipelineExecutionError
from noteforge.llm import create_llm_client
from noteforge.collector import collect_video
from noteforge.run import RunRecorder


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


def _subtitle_description(collection: VideoResource) -> str:
    track = collection.subtitles[0] if collection.subtitles else None
    transcript = collection.transcript
    if track is None or not transcript:
        return "没有可用字幕"
    kind = "自动字幕" if track.is_automatic else "人工字幕"
    return (
        f"{track.language} · {kind} · "
        f"{len(transcript):,} 个片段"
    )


def _run_preflight(
    ui: StatusUI,
    inspected: inspection.InspectionResult,
    *,
    cookies_from_browser: str | None,
    subtitle_language: str | None,
    subtitle_output_dir: Path,
) -> VideoResource:
    """在创建模型客户端前采集并验证视频字幕。"""

    if (
        inspected.platform not in {
            inspection.InspectionPlatform.BILIBILI,
            inspection.InspectionPlatform.YOUTUBE,
        }
        or inspected.normalized_source is None
    ):
        raise NoteForgeError("当前只支持标准 Bilibili 或 YouTube 视频 URL")

    with ui.running("检查输入", "正在获取视频和字幕信息..."):
        collection = collect_video(
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
    if not collection.transcript:
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
    run_id: str,
) -> None:
    ui.title("NoteForge")
    ui.info("来源", source)
    ui.info("输出", str(output))
    ui.info(
        "模型",
        f"{llm_api_format_label(settings.provider)} / {settings.model}",
    )
    ui.info("运行", run_id)
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
        None,
        "--cookies-from-browser",
        help="临时覆盖配置并从指定浏览器复用 Cookie；默认读取 config.yaml。",
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
    run_dir: Path = typer.Option(
        Path(".noteforge/runs"),
        "--run-dir",
        help="运行记录根目录。",
    ),
) -> None:
    """从视频字幕生成 Markdown 学习笔记。"""

    ui = StatusUI()
    renderer: PipelineRenderer | None = None
    recorder: RunRecorder | None = None
    try:
        inspected = inspection.inspect_source(source)
        output_path = output if output is not None else _default_output(inspected)
        recorder = RunRecorder.start(
            root=run_dir,
            source=source,
            source_id=inspected.source_id,
            platform=inspected.platform.value,
            normalized_source=inspected.normalized_source,
            page_number=inspected.page_number,
            output_path=output_path,
        )
        settings = load_configured_llm_settings()
        recorder.configure(
            api_format=settings.provider,
            model=settings.model,
            base_url=settings.base_url,
            llm_concurrency=llm_concurrency,
            subtitle_language=subtitle_language,
            cookie_strategy=cookies_from_browser or None,
        )
        _render_task(ui, source, output_path, settings, recorder.run_id)
        collection = _run_preflight(
            ui,
            inspected,
            cookies_from_browser=cookies_from_browser or None,
            subtitle_language=subtitle_language,
            subtitle_output_dir=subtitle_output_dir,
        )
        recorder.update_source(collection)
        recorder.save_artifact("transcript", collection.transcript)

        renderer = PipelineRenderer(verbose=verbose, show_header=False)
        client = create_llm_client(settings)
        pipeline = NoteGenerationPipeline.from_llm_client(
            client, max_concurrency=llm_concurrency
        )
        if hasattr(pipeline, "set_event_handler"):
            pipeline.set_event_handler(
                compose_event_handlers(renderer.handle, recorder.handle_event)
            )
        if hasattr(pipeline, "set_artifact_sink"):
            pipeline.set_artifact_sink(recorder)

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
        recorder.complete(written_path)
    except KeyboardInterrupt as error:
        if recorder is not None:
            recorder.cancel()
            ui.warning("运行取消", f"记录已保存：{recorder.run_dir}")
        raise typer.Exit(code=130) from error
    except PipelineExecutionError as error:
        if recorder is not None:
            recorder.fail(error)
        assert renderer is not None
        renderer.render_error(error, debug=debug)
        if debug:
            typer.echo("调试快照：.noteforge/debug/", err=True)
        if recorder is not None:
            ui.info("运行记录", str(recorder.run_dir))
        raise typer.Exit(code=1) from error
    except NoteForgeError as error:
        if recorder is not None:
            recorder.fail(error)
        ui.failure("生成失败", str(error))
        if recorder is not None:
            ui.info("运行记录", str(recorder.run_dir))
        raise typer.Exit(code=1) from error
    except Exception as error:
        if recorder is not None:
            recorder.fail(error)
        if debug:
            raise
        ui.failure("生成失败", "发生未预期错误；详细信息已保存到运行记录。")
        if recorder is not None:
            ui.info("运行记录", str(recorder.run_dir))
        raise typer.Exit(code=1) from error
    typer.echo(f"学习笔记已生成：{written_path}")
    assert recorder is not None
    typer.echo(f"运行记录：{recorder.run_dir}")
