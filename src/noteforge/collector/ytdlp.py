"""yt-dlp 采集器共用配置。"""

from typing import Any

from yt_dlp.networking.impersonate import ImpersonateTarget

_HTTP_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.bilibili.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


def build_ytdlp_options(
    cookies_from_browser: str | None = "chrome",
) -> dict[str, Any]:
    """构造元数据和字幕下载共用的安全配置。"""

    options: dict[str, Any] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreconfig": True,
        "noplaylist": True,
        # B站会校验 TLS/HTTP 客户端指纹，仅修改 User-Agent 仍可能触发 412。
        "impersonate": ImpersonateTarget(client="chrome"),
        "http_headers": dict(_HTTP_HEADERS),
    }
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser,)
    return options
