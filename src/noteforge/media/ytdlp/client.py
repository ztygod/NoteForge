"""与平台无关的 yt-dlp 执行和下载基础能力。"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadError

from noteforge.exceptions import CollectionError, RemoteCollectionError
from noteforge.media.config import PlatformConfig
from noteforge.media.ytdlp.errors import translate_download_error


class _QuietLogger:
    def debug(self, _: str) -> None: pass
    def info(self, _: str) -> None: pass
    def warning(self, _: str) -> None: pass
    def error(self, _: str) -> None: pass


YTDLP_LOGGER = _QuietLogger()


class YTDLPClient:
    """封装 yt-dlp 参数和调用细节，但不感知具体视频平台。"""

    def __init__(self, settings: PlatformConfig | None = None, *, extra_options: Mapping[str, Any] | None = None) -> None:
        self.settings = settings or PlatformConfig()
        self.extra_options = dict(extra_options or {})

    def options(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "quiet": True, "no_warnings": True, "logger": YTDLP_LOGGER,
            "ignoreconfig": True, "noplaylist": True, "skip_download": True,
            "writesubtitles": True, "writeautomaticsub": True,
            "impersonate": ImpersonateTarget(client="chrome"),
        }
        cookie_file = self.settings.cookie_file.expanduser() if self.settings.cookie_file else None
        if cookie_file:
            result["cookiefile"] = str(cookie_file)
            if not cookie_file.exists() and self.settings.cookies_from_browser:
                cookie_file.parent.mkdir(parents=True, exist_ok=True)
                result["cookiesfrombrowser"] = (self.settings.cookies_from_browser,)
        elif self.settings.cookies_from_browser:
            result["cookiesfrombrowser"] = (self.settings.cookies_from_browser,)
        if self.settings.proxy:
            result["proxy"] = self.settings.proxy
        result.update(self.extra_options)
        return result

    def extract_info(self, source: str, *, download: bool = False, options: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        params = self.options() | dict(options or {})
        try:
            with yt_dlp.YoutubeDL(params) as downloader:
                info = downloader.extract_info(source, download=download)
        except DownloadError as error:
            raise translate_download_error(error) from error
        except CollectionError:
            raise
        except Exception as error:
            raise RemoteCollectionError("视频资源提取时发生未知错误。") from error
        if not isinstance(info, Mapping):
            raise RemoteCollectionError("视频平台返回了无效数据。")
        return info

    def download_subtitle(self, source: str, *, language: str, subtitle_format: str, target_dir: Path) -> Mapping[str, Any]:
        target_dir.mkdir(parents=True, exist_ok=True)
        return self.extract_info(source, download=True, options={
            "subtitleslangs": [language], "subtitlesformat": f"{subtitle_format}/best",
            "outtmpl": {"default": str(target_dir / "subtitle.%(ext)s"), "subtitle": str(target_dir / "subtitle.%(ext)s")},
        })

    def download_media(self, source: str, *, target_dir: Path, audio_only: bool) -> Mapping[str, Any]:
        target_dir.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"skip_download": False, "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best", "outtmpl": str(target_dir / "%(id)s.%(ext)s")}
        if audio_only:
            options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        return self.extract_info(source, download=True, options=options)
