"""首次使用诊断命令。"""

import asyncio
from dataclasses import dataclass

import typer

from noteforge.cli.ui import StatusUI
from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.config import LLMSettings
from noteforge.exceptions import CollectionError, LLMConfigurationError
from noteforge.llm import LLMMessage, create_llm_client
from noteforge.subtitle.selector import SubtitleSelector


@dataclass(frozen=True, slots=True)
class _VideoCheckResult:
    """视频访问探测的最终状态。"""

    collection: VideoCollectionResult | None
    cookie_required: bool = False
    failed: bool = False


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


def _load_settings(ui: StatusUI) -> LLMSettings:
    """加载并展示 LLM 配置；缺少配置时结束命令。"""

    try:
        settings = LLMSettings.from_env()
    except ValueError as error:
        ui.failure("LLM 配置", str(error))
        ui.console.print("\n请先运行：\n  [bold]noteforge configure[/bold]")
        raise typer.Exit(code=1) from error
    ui.success("LLM 配置", f"{settings.provider} / {settings.model}")
    return settings


def _render_model_check(ui: StatusUI, settings: LLMSettings) -> bool:
    """检查模型并返回是否失败。"""

    try:
        with ui.running("模型调用", f"正在连接 {settings.model}..."):
            responding_model = asyncio.run(_check_model(settings))
    except Exception as error:
        ui.failure("模型调用", str(error))
        if settings.provider == "ollama":
            ui.console.print(
                "  请确认 Ollama 已启动且模型已安装：\n"
                "    ollama serve\n"
                f"    ollama pull {settings.model}"
            )
        else:
            ui.console.print("  请检查 API Key、模型名称、接口地址和网络连接。")
        return True
    ui.success("模型调用", f"可用（{responding_model}）")
    return False


def _collect_with_browser(
    ui: StatusUI,
    source: str,
    browser: str,
    *,
    failure_label: str,
    success_label: str,
    success_detail: str,
) -> _VideoCheckResult:
    """使用浏览器 Cookie 重试采集；期间不启用 spinner。"""

    try:
        collection = bilibili.get_bilibili_video_info(
            source,
            cookies_from_browser=browser,
        )
    except CollectionError as error:
        ui.failure(failure_label, str(error))
        return _VideoCheckResult(None, failed=True)
    ui.success(success_label, success_detail)
    return _VideoCheckResult(collection, cookie_required=True)


def _check_video_access(
    ui: StatusUI,
    source: str,
    browser: str,
) -> _VideoCheckResult:
    """先匿名探测；访问失败或无可用字幕时再使用 Cookie。"""

    try:
        with ui.running("匿名视频元数据", "正在检查 Bilibili..."):
            anonymous = bilibili.get_bilibili_video_info(
                source,
                cookies_from_browser=None,
            )
    except CollectionError as error:
        if not browser:
            ui.failure("访问权限", str(error))
            return _VideoCheckResult(None, failed=True)
        ui.warning(
            "匿名访问",
            f"失败，正在使用 {browser} 浏览器 Cookie 重试",
        )
        ui.console.print(
            "  [dim]macOS 可能请求钥匙串授权，请按系统提示操作。[/dim]"
        )
        return _collect_with_browser(
            ui,
            source,
            browser,
            failure_label="访问权限",
            success_label="访问权限",
            success_detail=f"需要 {browser} 浏览器 Cookie",
        )

    ui.success("匿名视频元数据", "无需浏览器 Cookie")
    if SubtitleSelector().select(anonymous.subtitle_tracks) is not None:
        ui.success("获取视频字幕", "无需浏览器 Cookie")
        return _VideoCheckResult(anonymous)
    if not browser:
        return _VideoCheckResult(anonymous)

    ui.warning(
        "匿名字幕",
        f"未发现 VTT/SRT，正在使用 {browser} 浏览器 Cookie 重试",
    )
    ui.console.print(
        "  [dim]视频可以匿名访问，但字幕轨道可能需要登录；"
        "macOS 可能请求钥匙串授权。[/dim]"
    )
    result = _collect_with_browser(
        ui,
        source,
        browser,
        failure_label="字幕权限",
        success_label="字幕权限",
        success_detail=f"已使用 {browser} 浏览器 Cookie 重新检查",
    )
    if result.failed:
        # 匿名结果仍可用于展示视频信息和已发现的轨道。
        return _VideoCheckResult(anonymous, failed=True)
    return result


def _render_video_and_subtitle(
    ui: StatusUI,
    collection: VideoCollectionResult,
) -> bool:
    """展示视频与字幕并返回字幕是否不可用。"""

    ui.success("视频标题", collection.metadata.title)
    selected = SubtitleSelector().select(collection.subtitle_tracks)
    if selected is not None:
        kind = "自动字幕" if selected.is_automatic else "人工字幕"
        ui.success(
            "字幕",
            f"{selected.language} · {kind} · {selected.extension.upper()}",
        )
        return False

    discovered_formats = sorted({
        track.extension.upper()
        for track in collection.subtitle_tracks
    })
    detail = "没有发现当前支持的 VTT 或 SRT 字幕"
    if discovered_formats:
        detail += f"（发现的其他轨道：{', '.join(discovered_formats)}）"
    ui.failure("字幕", detail)
    return True


def _generation_command(
    url: str,
    browser: str,
    *,
    cookie_required: bool,
) -> str:
    """构造与诊断结果一致的生成命令。"""

    command = f"noteforge generate {_quoted(url)}"
    if not cookie_required:
        return command + ' --cookies-from-browser ""'
    if browser != "chrome":
        return command + f" --cookies-from-browser {browser}"
    return command


def _quoted(value: str) -> str:
    """生成适合复制到常见 shell 的单引号参数。"""

    return "'" + value.replace("'", "'\"'\"'") + "'"


def _render_ready(ui: StatusUI, command: str) -> None:
    ui.console.print("\n[bold green]准备就绪[/bold green]\n")
    ui.console.print(f"  [bold]{command}[/bold]", soft_wrap=True)


def _render_missing_video(ui: StatusUI) -> None:
    ui.warning("视频字幕", "未提供 URL，尚未检查 Cookie 和字幕")
    ui.console.print(
        "\n继续检查某个视频：\n"
        "  [bold]noteforge doctor 'https://www.bilibili.com/video/BV...'[/bold]"
    )


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

    ui = StatusUI()
    ui.title("NoteForge Doctor")
    ui.section("环境")
    settings = _load_settings(ui)
    failed = _render_model_check(ui, settings)

    if url is None:
        _render_missing_video(ui)
    else:
        ui.section("视频")
        inspected = inspection.inspect_source(url)
        if (
            inspected.platform is not inspection.InspectionPlatform.BILIBILI
            or inspected.normalized_source is None
        ):
            ui.failure("视频来源", "当前只支持标准 B 站视频 URL")
            failed = True
        else:
            result = _check_video_access(
                ui,
                inspected.normalized_source,
                cookies_from_browser,
            )
            failed = failed or result.failed
            if result.collection is not None:
                failed = (
                    _render_video_and_subtitle(ui, result.collection)
                    or failed
                )
                if not failed:
                    _render_ready(
                        ui,
                        _generation_command(
                            url,
                            cookies_from_browser,
                            cookie_required=result.cookie_required,
                        ),
                    )

    if failed:
        raise typer.Exit(code=1)
