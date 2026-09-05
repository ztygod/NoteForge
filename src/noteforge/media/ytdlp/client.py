"""与平台无关的 yt-dlp 执行和下载基础能力。"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadError

from noteforge.exceptions import CollectionError, RemoteCollectionError
from noteforge.media.ytdlp.errors import translate_download_error


class _QuietLogger:
    """阻止 yt-dlp 把可能含 URL 或认证上下文的信息写入应用日志。"""

    def debug(self, _: str) -> None:
        pass

    def info(self, _: str) -> None:
        pass

    def warning(self, _: str) -> None:
        pass

    def error(self, _: str) -> None:
        pass


YTDLP_LOGGER = _QuietLogger()


class YTDLPClient:
    """封装 yt-dlp 参数和调用细节，但不感知具体视频平台。"""

    def __init__(
        self,
        *,
        extra_options: Mapping[str, Any] | None = None,
    ) -> None:
        self.extra_options = dict(extra_options or {})

    def options(self) -> dict[str, Any]:
        """构造安全默认选项；调用方无法直接传入该结构。"""

        result: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "logger": YTDLP_LOGGER,
            "ignoreconfig": True,
            "noplaylist": True,
            "skip_download": True,
            # 元数据和字幕发现不应因为缺少可下载的媒体格式而失败。
            "ignore_no_formats_error": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "impersonate": ImpersonateTarget(client="chrome"),
        }
        result.update(self.extra_options)
        return result

    def extract_info(
        self,
        source: str,
        *,
        download: bool = False,
        options: Mapping[str, Any] | None = None,
        cookie_file: Path | None = None,
    ) -> Mapping[str, Any]:
        """执行一次 yt-dlp 提取，并统一翻译后端异常。"""

        params = self.options() | dict(options or {})
        if cookie_file is not None:
            params["cookiefile"] = str(cookie_file)
        try:
            # yt-dlp 的公开 Python API 接受动态参数字典，但其类型信息把参数
            # 标注为不可公开导入的内部 _Params。仅在第三方库边界放宽类型，
            # 避免让 Any 扩散到本模块的参数构造与业务返回值中。
            with yt_dlp.YoutubeDL(cast(Any, params)) as downloader:
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

    def download_subtitle(
        self,
        source: str,
        *,
        language: str,
        subtitle_format: str,
        target_dir: Path,
        cookie_file: Path | None = None,
    ) -> Mapping[str, Any]:
        """下载单条指定字幕到 Worker 分配的临时目录。"""

        target_dir.mkdir(parents=True, exist_ok=True)
        return self.extract_info(
            source,
            download=True,
            options={
                "subtitleslangs": [language],
                "subtitlesformat": f"{subtitle_format}/best",
                "outtmpl": {
                    "default": str(target_dir / "subtitle.%(ext)s"),
                    "subtitle": str(target_dir / "subtitle.%(ext)s"),
                },
            },
            cookie_file=cookie_file,
        )

    def download_media(
        self,
        source: str,
        *,
        target_dir: Path,
        audio_only: bool,
        format_id: str | None = None,
        codec: str = "mp3",
        cookie_file: Path | None = None,
    ) -> Mapping[str, Any]:
        """下载视频或提取音频；格式选择由领域请求映射而来。"""

        target_dir.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {
            "skip_download": False,
            # 真正下载媒体时必须存在匹配格式，不能沿用发现阶段的宽松策略。
            "ignore_no_formats_error": False,
            "format": format_id
            or ("bestaudio/best" if audio_only else "bestvideo+bestaudio/best"),
            "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        }
        if audio_only:
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": codec}
            ]
        return self.extract_info(
            source, download=True, options=options, cookie_file=cookie_file
        )
