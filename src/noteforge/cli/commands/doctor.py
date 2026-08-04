"""首次使用诊断命令。"""

import asyncio

import typer

from noteforge.collector import bilibili, inspection
from noteforge.config import LLMSettings
from noteforge.exceptions import CollectionError, LLMConfigurationError
from noteforge.llm import LLMMessage, create_llm_client
from noteforge.subtitle.selector import SubtitleSelector


def _success(label: str, detail: str) -> None:
    typer.secho("✓ ", fg=typer.colors.GREEN, nl=False)
    typer.echo(f"{label:<8}{detail}")


def _warning(label: str, detail: str) -> None:
    typer.secho("! ", fg=typer.colors.YELLOW, nl=False)
    typer.echo(f"{label:<8}{detail}")


def _failure(label: str, detail: str) -> None:
    typer.secho("✗ ", fg=typer.colors.RED, nl=False)
    typer.echo(f"{label:<8}{detail}")


async def _check_model(settings: LLMSettings) -> str:
    """发送一个最小请求，确认服务与指定模型均可调用。"""

    client = create_llm_client(settings)
    try:
        response = await client.generate(
            (LLMMessage("user", "只回复 OK。"),)
        )
    finally:
        await client.aclose()
    if not response.content.strip():
        raise LLMConfigurationError("模型返回了空响应")
    return response.model


def _quoted(value: str) -> str:
    """生成适合复制到常见 shell 的单引号参数。"""

    return "'" + value.replace("'", "'\"'\"'") + "'"


def doctor(
    url: str | None = typer.Argument(
        None,
        help="可选的视频 URL；提供后会同时检查访问权限和字幕。",
    ),
    cookies_from_browser: str = typer.Option(
        "chrome",
        "--cookies-from-browser",
        help="无 Cookie 访问失败后，用于重试的已登录浏览器。",
    ),
) -> None:
    """检查配置、模型以及目标视频是否已具备生成条件。"""

    typer.secho("NoteForge 首次使用检查\n", bold=True)
    failed = False

    try:
        settings = LLMSettings.from_env()
    except ValueError as error:
        _failure("LLM 配置", str(error))
        typer.echo("\n请先运行：\n  noteforge configure")
        raise typer.Exit(code=1) from error

    _success("LLM 配置", f"{settings.provider} / {settings.model}")
    try:
        responding_model = asyncio.run(_check_model(settings))
    except Exception as error:
        failed = True
        _failure("模型调用", str(error))
        if settings.provider == "ollama":
            typer.echo(
                "  请确认 Ollama 已启动且模型已安装：\n"
                "    ollama serve\n"
                f"    ollama pull {settings.model}"
            )
        else:
            typer.echo("  请检查 API Key、模型名称、接口地址和网络连接。")
    else:
        _success("模型调用", f"可用（{responding_model}）")

    if url is not None:
        inspected = inspection.inspect_source(url)
        if (
            inspected.platform is not inspection.InspectionPlatform.BILIBILI
            or inspected.normalized_source is None
        ):
            failed = True
            _failure("视频来源", "当前只支持标准 B 站视频 URL")
        else:
            collection = None
            cookie_required = False
            try:
                collection = bilibili.get_bilibili_video_info(
                    inspected.normalized_source,
                    cookies_from_browser=None,
                )
                _success("访问权限", "无需浏览器 Cookie")
            except CollectionError as no_cookie_error:
                if not cookies_from_browser:
                    failed = True
                    _failure("访问权限", str(no_cookie_error))
                else:
                    _warning(
                        "匿名访问",
                        f"失败，正在使用 {cookies_from_browser} 浏览器 Cookie 重试",
                    )
                    try:
                        collection = bilibili.get_bilibili_video_info(
                            inspected.normalized_source,
                            cookies_from_browser=cookies_from_browser,
                        )
                    except CollectionError as cookie_error:
                        failed = True
                        _failure("访问权限", str(cookie_error))
                    else:
                        cookie_required = True
                        _success(
                            "访问权限",
                            f"需要 {cookies_from_browser} 浏览器 Cookie",
                        )

            if collection is not None:
                _success("视频", collection.metadata.title)
                selected = SubtitleSelector().select(collection.subtitle_tracks)
                if selected is None:
                    failed = True
                    discovered_formats = sorted({
                        track.extension.upper()
                        for track in collection.subtitle_tracks
                    })
                    detail = "没有发现当前支持的 VTT 或 SRT 字幕"
                    if discovered_formats:
                        detail += f"（发现的其他轨道：{', '.join(discovered_formats)}）"
                    _failure("字幕", detail)
                else:
                    kind = "自动字幕" if selected.is_automatic else "人工字幕"
                    _success("字幕", f"{selected.language} · {kind} · {selected.extension.upper()}")

                if not failed:
                    command = f"noteforge generate {_quoted(url)}"
                    if not cookie_required:
                        command += ' --cookies-from-browser ""'
                    elif cookies_from_browser != "chrome":
                        command += f" --cookies-from-browser {cookies_from_browser}"
                    typer.echo(f"\n检查通过，可以开始生成：\n  {command}")
    else:
        _warning("视频字幕", "未提供 URL，尚未检查 Cookie 和字幕")
        typer.echo(
            "\n继续检查某个视频：\n"
            "  noteforge doctor 'https://www.bilibili.com/video/BV...'")

    if failed:
        raise typer.Exit(code=1)
