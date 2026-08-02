"""generate 子命令。"""

import asyncio
from pathlib import Path

import typer

from noteforge.cli.configuration import create_configured_llm_client
from noteforge.cli.renderer import PipelineRenderer
from noteforge.core import NoteGenerationPipeline
from noteforge.exceptions import NoteForgeError, PipelineExecutionError


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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="显示阶段指标与耗时。"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="失败时保存中间数据并显示原始异常。"
    ),
) -> None:
    """从视频字幕生成 Markdown 学习笔记。"""

    renderer = PipelineRenderer(verbose=verbose)
    try:
        client = create_configured_llm_client()
        pipeline = NoteGenerationPipeline.from_llm_client(client)
        if hasattr(pipeline, "set_event_handler"):
            pipeline.set_event_handler(renderer.handle)
        written_path = asyncio.run(
            pipeline.run(
                source,
                output,
                cookies_from_browser=cookies_from_browser or None,
                subtitle_language=subtitle_language,
                subtitle_output_dir=subtitle_output_dir,
                **({"debug_dir": Path(".noteforge/debug")} if debug else {}),
            )
        )
    except PipelineExecutionError as error:
        renderer.render_error(error, debug=debug)
        if debug:
            typer.echo("调试快照：.noteforge/debug/", err=True)
        raise typer.Exit(code=1) from error
    except NoteForgeError as error:
        typer.secho(f"生成失败：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"学习笔记已生成：{written_path}")

