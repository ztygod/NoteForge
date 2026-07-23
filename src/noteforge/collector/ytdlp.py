"""yt-dlp 采集器共用配置。"""

from typing import Any

from yt_dlp.networking.impersonate import ImpersonateTarget

_HTTP_HEADERS = {
    # 声明能够接收浏览器页面常见的内容类型，降低被平台识别为脚本的概率。
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    # 优先请求中文内容，并为平台的地区和语言判断提供浏览器特征。
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    # B站部分接口会校验来源页面。
    "Referer": "https://www.bilibili.com/",
    # 使用常见桌面浏览器标识，避免默认 Python User-Agent 触发风控。
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
        # 禁止下载视频和音频；字幕下载阶段也必须始终保持为 True。
        "skip_download": True,
        # 不输出 yt-dlp 的常规进度信息，由 NoteForge 统一负责用户输出。
        "quiet": True,
        # 不直接打印 yt-dlp 警告，避免污染 CLI 的结构化输出。
        "no_warnings": True,
        # 忽略用户目录中的 yt-dlp 配置，保证程序行为可预测。
        "ignoreconfig": True,
        # 每次只处理传入 URL 对应的视频或分 P，不展开合集和播放列表。
        "noplaylist": True,
        # B站会校验 TLS/HTTP 客户端指纹，仅修改 User-Agent 仍可能触发 412。
        "impersonate": ImpersonateTarget(client="chrome"),
        # 为元数据查询和字幕请求提供一致的浏览器请求头。
        "http_headers": dict(_HTTP_HEADERS),
        # 通知平台提取器查询人工字幕信息。
        # collect() 使用 download=False，因此这里只发现字幕，不会写文件。
        "writesubtitles": True,
        # 同时查询自动生成字幕，例如 B站的 ai-zh 和 ai-en。
        "writeautomaticsub": True,
    }
    if cookies_from_browser:
        # 读取指定浏览器 Cookie，用于登录字幕和降低 B站 412 风控概率。
        options["cookiesfrombrowser"] = (cookies_from_browser,)
    return options
