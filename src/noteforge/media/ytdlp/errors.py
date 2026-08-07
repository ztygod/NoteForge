"""在不引入平台策略的前提下转换 yt-dlp 异常。"""

from yt_dlp.utils import DownloadError

from noteforge.exceptions import CollectionError, LoginRequiredError, RemoteCollectionError, RiskControlError, UnsupportedSourceError, VideoUnavailableError


def translate_download_error(error: DownloadError) -> CollectionError:
    message = str(error)
    normalized = message.casefold()
    if "unsupported url" in normalized or "no suitable extractor" in normalized:
        return UnsupportedSourceError(f"不支持的视频 URL：{message}")
    if any(item in normalized for item in ("login required", "sign in", "cookies", "扫码登录", "登录后")):
        return LoginRequiredError(f"该视频需要登录后访问：{message}")
    if "http error 412" in normalized or "risk control" in normalized or "风控" in message:
        return RiskControlError(f"视频平台触发访问风控：{message}")
    if any(item in normalized for item in ("video unavailable", "video is unavailable", "does not exist", "private video", "不存在")):
        return VideoUnavailableError(f"视频不存在或不可访问：{message}")
    return RemoteCollectionError(f"视频资源提取失败：{message}")
