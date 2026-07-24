"""yt-dlp 采集器共用配置。"""

from collections.abc import Mapping
from typing import Any

from yt_dlp.networking.impersonate import ImpersonateTarget

def build_ytdlp_options(
    cookies_from_browser: str | None = "chrome",
    *,
    http_headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """构造跨平台的 yt-dlp 基础配置。"""

    options: dict[str, Any] = {
        # 禁止下载视频和音频；字幕下载阶段也必须始终保持为 True。
        "skip_download": True,
        # 不输出 yt-dlp 的常规进度信息，由 NoteForge 统一负责用户输出。
        "quiet": False,
        # 不直接打印 yt-dlp 警告，避免污染 CLI 的结构化输出。
        "no_warnings": True,
        # 忽略用户目录中的 yt-dlp 配置，保证程序行为可预测。
        "ignoreconfig": True,
        # 每次只处理传入 URL 对应的视频或分 P，不展开合集和播放列表。
        "noplaylist": True,
        # 使用 curl-cffi 同时模拟 TLS 指纹和配套浏览器请求头。
        # 不手写 Accept/User-Agent，避免与实际模拟的 Chrome 版本冲突。
        "impersonate": ImpersonateTarget(client="chrome"),
        # 所有 NoteForge 采集流程都需要查询人工字幕和自动字幕。
        "writesubtitles": True,
        "writeautomaticsub": True,
    }
    if http_headers:
        # 平台专属 Header 由调用方提供，避免通用配置绑定 Bilibili。
        options["http_headers"] = dict(http_headers)
    if cookies_from_browser:
        # 读取指定浏览器 Cookie，用于登录字幕和降低 B站 412 风控概率。
        options["cookiesfrombrowser"] = (cookies_from_browser,)
    return options
