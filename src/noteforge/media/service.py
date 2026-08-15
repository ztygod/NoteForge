"""统一媒体服务，是应用层唯一允许调用的媒体入口。"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from noteforge.exceptions import RemoteCollectionError, UnsupportedSourceError
from noteforge.media.assets import AssetReference, MediaAsset
from noteforge.media.config import ExtractorConfig, load_extractor_config
from noteforge.media.cookies import CookieService
from noteforge.media.models import (
    AudioRequest,
    AuthRequest,
    Browser,
    MediaFormats,
    MediaType,
    Playlist,
    Subtitle,
    SubtitleRequest,
    VideoMetadata,
    VideoRequest,
    VideoResource,
)
from noteforge.media.platforms import BilibiliAdapter, PlatformAdapter, YouTubeAdapter
from noteforge.media.protocols import AudioTranscriber, MediaWorker
from noteforge.media.repository import MediaRepository
from noteforge.media.subtitle import SubtitleParser
from noteforge.media.worker import ProcessMediaWorker


class MediaService:
    """统一编排平台识别、认证租约、Worker 和资产生命周期。"""

    def __init__(
        self,
        config: ExtractorConfig | None = None,
        *,
        cookie_service: CookieService | None = None,
        worker: MediaWorker | None = None,
        transcriber: AudioTranscriber | None = None,
        asset_ttl: timedelta = timedelta(hours=1),
    ) -> None:
        self.config = config or ExtractorConfig()
        # Repository 只持久化元数据/文本；媒体二进制始终进入临时资产目录。
        self.repository = MediaRepository(self.config.cache_path)
        self.cookies = cookie_service or CookieService(
            vault_root=self.config.credential_vault_path
        )
        self.worker = worker or ProcessMediaWorker(self.config.worker_count)
        self.transcriber = transcriber
        self.asset_ttl = asset_ttl
        self._legacy_assets: list[MediaAsset] = []
        self._adapters: tuple[PlatformAdapter, ...] = (
            BilibiliAdapter(),
            YouTubeAdapter(),
        )

    def supports(self, source: str) -> bool:
        """判断任一已注册平台是否支持该来源。"""

        return any(adapter.supports(source) for adapter in self._adapters)

    def extract_metadata(
        self, source: str, *, auth: AuthRequest | None = None
    ) -> VideoMetadata:
        """提取并标准化元数据，不下载媒体正文。"""

        adapter, normalized = self._resolve(source)
        info = self._extract(adapter, normalized, auth=auth)
        metadata = adapter.metadata(info, normalized)
        self.repository.save_metadata(metadata)
        return metadata

    def list_formats(
        self, source: str, *, auth: AuthRequest | None = None
    ) -> MediaFormats:
        """列出标准化格式，不向调用方暴露 yt-dlp 参数结构。"""

        adapter, normalized = self._resolve(source)
        return adapter.formats(self._extract(adapter, normalized, auth=auth))

    def list_subtitles(
        self, source: str, *, auth: AuthRequest | None = None
    ) -> tuple[Subtitle, ...]:
        """列出人工与自动字幕轨道。"""

        adapter, normalized = self._resolve(source)
        return adapter.subtitles(self._extract(adapter, normalized, auth=auth))

    def extract_playlist(
        self, source: str, *, auth: AuthRequest | None = None
    ) -> Playlist:
        """以轻量模式提取播放列表，避免递归下载条目。"""

        adapter, normalized = self._resolve(source)
        info = self._extract(
            adapter,
            normalized,
            auth=auth,
            options={"noplaylist": False, "extract_flat": True},
        )
        return adapter.playlist(info, normalized)

    def download_video(
        self,
        source: str,
        request: VideoRequest | None = None,
        *,
        auth: AuthRequest | None = None,
    ) -> MediaAsset:
        """下载视频并返回必须关闭的临时资产。"""

        return self._download_media(source, request or VideoRequest(), False, auth)

    def download_audio(
        self,
        source: str,
        request: AudioRequest | None = None,
        *,
        auth: AuthRequest | None = None,
    ) -> MediaAsset:
        """下载并按请求转码音频，结果受资产租约控制。"""

        return self._download_media(source, request or AudioRequest(), True, auth)

    def download_subtitle(
        self,
        source: str,
        request: SubtitleRequest,
        *,
        auth: AuthRequest | None = None,
    ) -> MediaAsset:
        """下载指定字幕轨道，异常时立即回收临时目录。"""

        adapter, normalized = self._resolve(source)
        metadata = self.extract_metadata(normalized, auth=auth)
        root = self._asset_root()
        try:
            with self.cookies.acquire(adapter.platform, auth) as credential:
                info = self.worker.execute(
                    {
                        "operation": "download_subtitle",
                        "source": normalized,
                        "target_dir": str(root),
                        "language": request.language,
                        "subtitle_format": request.format,
                        "cookie_file": self._credential_path(credential),
                        "platform_options": dict(adapter.backend_options()),
                    }
                )
            requested = info.get("requested_subtitles")
            item = (
                requested.get(request.language)
                if isinstance(requested, Mapping)
                else None
            )
            path_value = item.get("filepath") if isinstance(item, Mapping) else None
            if not isinstance(path_value, str):
                raise RemoteCollectionError("媒体 Worker 未返回字幕文件。")
            return self._asset(MediaType.SUBTITLE, metadata, Path(path_value), root)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def discover(
        self, source: str, *, auth: AuthRequest | None = None
    ) -> VideoResource:
        """聚合元数据和字幕轨道，不返回后端原始对象。"""

        adapter, normalized = self._resolve(source)
        info = self._extract(adapter, normalized, auth=auth)
        metadata = adapter.metadata(info, normalized)
        self.repository.save_metadata(metadata)
        return VideoResource(metadata=metadata, subtitles=adapter.subtitles(info))

    def extract(
        self,
        source: str,
        *,
        subtitle_language: str | None = None,
        download_audio: bool = False,
        download_video: bool = False,
        auth: AuthRequest | None = None,
    ) -> VideoResource:
        """为笔记流水线生成字幕转录，必要时回退到音频转写。"""

        resource = self.discover(source, auth=auth)
        metadata = resource.metadata
        transcript = (
            self.repository.load_transcript(metadata.platform, metadata.id) or ()
        )
        transcript_source = "cache" if transcript else None
        subtitles = resource.subtitles
        selected = (
            self.select_subtitle(subtitles, subtitle_language)
            if not transcript
            else None
        )
        if selected:
            if selected.content is not None:
                transcript = SubtitleParser().parse(selected)
            else:
                with self.download_subtitle(
                    source,
                    SubtitleRequest(selected.language, selected.format),
                    auth=auth,
                ) as asset:
                    selected = Subtitle(
                        selected.language,
                        selected.format,
                        content=asset.path.read_text(encoding="utf-8"),
                        is_automatic=selected.is_automatic,
                    )
                    transcript = SubtitleParser().parse(selected)
            self.repository.save_transcript(metadata, transcript)
            transcript_source = (
                "automatic_subtitle" if selected.is_automatic else "manual_subtitle"
            )
        audio_asset = self.download_audio(source, auth=auth) if download_audio else None
        if not transcript and self.transcriber:
            owned = audio_asset or self.download_audio(source, auth=auth)
            try:
                transcript = self.transcriber.transcribe(
                    owned.path, language=subtitle_language
                )
                self.repository.save_transcript(metadata, transcript)
                transcript_source = "whisper"
            finally:
                if audio_asset is None:
                    owned.close()
        video_asset = self.download_video(source, auth=auth) if download_video else None
        self._legacy_assets.extend(
            asset for asset in (audio_asset, video_asset) if asset is not None
        )
        # 兼容旧对象时由调用方负责本次进程内路径；新代码应直接使用 MediaAsset。
        return VideoResource(
            metadata,
            subtitles,
            transcript,
            audio_asset.path if audio_asset else None,
            video_asset.path if video_asset else None,
            transcript_source,
        )

    @staticmethod
    def select_subtitle(
        subtitles: tuple[Subtitle, ...], preferred: str | None
    ) -> Subtitle | None:
        """优先人工、指定语言和更易解析的字幕格式。"""

        order = {"vtt": 0, "srt": 1, "ass": 2, "json3": 3}
        candidates = [item for item in subtitles if item.format in order]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (
                item.is_automatic,
                0
                if preferred and item.language.casefold() == preferred.casefold()
                else 1,
                order[item.format],
            ),
        )

    def cleanup(self) -> int:
        """清理 Cookie 与媒体的崩溃遗留租约，返回删除数量。"""

        removed = self.cookies.cleanup_expired()
        cutoff = datetime.now(UTC) - self.asset_ttl
        if not self.config.runtime_path.exists():
            return removed
        for path in self.config.runtime_path.glob("asset-*"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            except OSError:
                continue
            if modified < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        return removed

    def close(self) -> None:
        """回收兼容资产并关闭 Worker 池；可重复调用。"""

        for asset in self._legacy_assets:
            asset.close()
        self._legacy_assets.clear()
        self.worker.close()

    def __enter__(self) -> MediaService:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _resolve(self, source: str) -> tuple[PlatformAdapter, str]:
        """选择平台适配器并返回规范化 URL。"""

        for adapter in self._adapters:
            if adapter.supports(source):
                return adapter, adapter.normalize(source)
        raise UnsupportedSourceError(f"不支持的视频 URL：{source}")

    def _extract(
        self,
        adapter: PlatformAdapter,
        source: str,
        *,
        auth: AuthRequest | None,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """在 Cookie 租约范围内执行只读发现操作。"""

        with self.cookies.acquire(adapter.platform, auth) as credential:
            return self.worker.execute(
                {
                    "operation": "extract",
                    "source": source,
                    "options": dict(options or {}),
                    "cookie_file": self._credential_path(credential),
                    "platform_options": dict(adapter.backend_options())
                    | self._proxy_options(adapter),
                }
            )

    def _download_media(
        self,
        source: str,
        request: VideoRequest | AudioRequest,
        audio_only: bool,
        auth: AuthRequest | None,
    ) -> MediaAsset:
        """执行媒体下载并把 Worker 文件包装成受控资产。"""

        adapter, normalized = self._resolve(source)
        metadata = self.extract_metadata(normalized, auth=auth)
        root = self._asset_root()
        try:
            with self.cookies.acquire(adapter.platform, auth) as credential:
                info = self.worker.execute(
                    {
                        "operation": "download_media",
                        "source": normalized,
                        "target_dir": str(root),
                        "audio_only": audio_only,
                        "format_id": request.format_id,
                        "codec": request.codec
                        if isinstance(request, AudioRequest)
                        else "mp3",
                        "cookie_file": self._credential_path(credential),
                        "platform_options": dict(adapter.backend_options())
                        | self._proxy_options(adapter),
                    }
                )
            path = self._downloaded_path(info, audio_only, request)
            return self._asset(
                MediaType.AUDIO if audio_only else MediaType.VIDEO, metadata, path, root
            )
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def _proxy_options(self, adapter: PlatformAdapter) -> dict[str, Any]:
        proxy = self.config.for_platform(adapter.platform.value).proxy
        return {"proxy": proxy} if proxy else {}

    @staticmethod
    def _credential_path(credential: Any) -> str | None:
        path = credential._materialize_for_backend()
        return str(path) if path else None

    def _asset_root(self) -> Path:
        self.config.runtime_path.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="asset-", dir=self.config.runtime_path))

    def _asset(
        self, media_type: MediaType, metadata: VideoMetadata, path: Path, root: Path
    ) -> MediaAsset:
        reference = AssetReference(
            uuid.uuid4().hex,
            media_type,
            datetime.now(UTC) + self.asset_ttl,
            metadata,
        )
        return MediaAsset(reference, path, root)

    @staticmethod
    def _downloaded_path(
        info: Mapping[str, Any], audio_only: bool, request: VideoRequest | AudioRequest
    ) -> Path:
        downloads = info.get("requested_downloads")
        value = (
            downloads[0].get("filepath")
            if isinstance(downloads, list)
            and downloads
            and isinstance(downloads[0], Mapping)
            else info.get("_filename")
        )
        if not isinstance(value, str) or not value:
            raise RemoteCollectionError("媒体 Worker 未返回下载文件路径。")
        path = Path(value)
        if audio_only and isinstance(request, AudioRequest):
            converted = path.with_suffix(f".{request.codec}")
            if converted.exists():
                return converted
        return path


def _auth(browser: str | None) -> AuthRequest | None:
    return AuthRequest(Browser(browser)) if browser else None


def collect_video(
    source: str,
    *,
    cookies_from_browser: str | None = None,
    subtitle_language: str | None = None,
    subtitle_output_dir: Path | None = None,
    page_number: int | None = None,
) -> VideoResource:
    """CLI/流水线使用的媒体便捷入口。"""

    del page_number
    configured = load_extractor_config()
    config = ExtractorConfig(
        cache_path=subtitle_output_dir or configured.cache_path,
        platforms=configured.platforms,
        runtime_path=configured.runtime_path,
        credential_vault_path=configured.credential_vault_path,
        worker_count=configured.worker_count,
    )
    with MediaService(config) as media:
        return media.extract(
            source,
            subtitle_language=subtitle_language,
            auth=_auth(cookies_from_browser),
        )


def discover_video(
    source: str, *, cookies_from_browser: str | None = None
) -> VideoResource:
    """CLI 诊断使用的媒体发现入口。"""

    with MediaService(load_extractor_config()) as media:
        return media.discover(source, auth=_auth(cookies_from_browser))
