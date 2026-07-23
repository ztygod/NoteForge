"""使用 yt-dlp 采集 B站视频元数据并转换平台错误。"""

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadError

from noteforge.collector.base import Collector
from noteforge.collector.models import VideoMetadata
from noteforge.exceptions import (
    CollectionError,
    LoginRequiredError,
    RemoteCollectionError,
    RiskControlError,
    UnsupportedSourceError,
    VideoUnavailableError,
)

_YDL_OPTIONS = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "ignoreconfig": True,
    "noplaylist": True,
    # B站会校验 TLS/HTTP 客户端指纹，仅修改 User-Agent 仍可能触发 412。
    "impersonate": ImpersonateTarget(client="chrome"),
    "http_headers": {
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
    },
}


# 兼容现有调用方；新代码应直接使用通用的 VideoMetadata。
BilibiliCollectorResult = VideoMetadata


def _translate_download_error(error: DownloadError) -> CollectionError:
    message = str(error)
    normalized = message.casefold()

    if "unsupported url" in normalized or "no suitable extractor" in normalized:
        return UnsupportedSourceError(f"不支持的视频 URL：{message}")
    if any(
        marker in normalized
        for marker in (
            "login required",
            "sign in",
            "cookies",
            "扫码登录",
            "登录后",
        )
    ):
        return LoginRequiredError(f"该视频需要登录后访问：{message}")
    if (
        "http error 412" in normalized
        or "risk control" in normalized
        or "风控" in message
    ):
        return RiskControlError(
            "视频平台触发访问风控（HTTP 412）；可尝试使用 "
            "--cookies-from-browser 指定已登录的浏览器。"
            f"原始错误：{message}"
        )
    if any(
        marker in normalized
        for marker in (
            "video is unavailable",
            "video unavailable",
            "does not exist",
            "not available",
            "private video",
            "已失效",
            "不存在",
            "不可见",
        )
    ):
        return VideoUnavailableError(f"视频不存在或不可访问：{message}")
    if any(
        marker in normalized
        for marker in ("timed out", "timeout", "connection timeout")
    ):
        return RemoteCollectionError(f"连接视频平台超时：{message}")
    return RemoteCollectionError(f"远程采集视频元数据失败：{message}")


class BilibiliCollector(Collector[VideoMetadata]):
    """B站视频信息采集器。"""

    def __init__(self, cookies_from_browser: str | None = "chrome") -> None:
        self._cookies_from_browser = cookies_from_browser

    def collect(self, source: str) -> VideoMetadata:
        """根据完整视频 URL 采集结构化元数据。"""

        options = dict(_YDL_OPTIONS)
        if self._cookies_from_browser:
            options["cookiesfrombrowser"] = (self._cookies_from_browser,)

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(source, download=False)
        except DownloadError as error:
            raise _translate_download_error(error) from error
        except Exception as error:
            raise RemoteCollectionError("远程采集视频元数据时发生未知错误。") from error

        return VideoMetadata.from_mapping(info)


def get_bilibili_video_info(source: str) -> VideoMetadata:
    """根据完整视频 URL 获取 B站视频元数据。"""

    return BilibiliCollector().collect(source)
