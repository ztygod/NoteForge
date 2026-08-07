"""不同视频平台采集器共享的应用流程。"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from noteforge.media.cache import MediaCache
from noteforge.media.config import ExtractorConfig
from noteforge.media.models import Subtitle, VideoMetadata, VideoPlatform, VideoResource
from noteforge.media.subtitle import SubtitleParser
from noteforge.media.transcriber import AudioTranscriber
from noteforge.media.ytdlp import YTDLPClient


class PlatformCollector(ABC):
    platform: str

    def __init__(self, config: ExtractorConfig | None = None, *, transcriber: AudioTranscriber | None = None) -> None:
        self.config = config or ExtractorConfig()
        self.cache = MediaCache(self.config.cache_path)
        self.transcriber = transcriber
        self.client = YTDLPClient(
            self.config.for_platform(self.platform),
            extra_options=self.ytdlp_options(),
        )

    @abstractmethod
    def supports(self, source: str) -> bool: ...

    @abstractmethod
    def normalize(self, source: str) -> str: ...

    def ytdlp_options(self) -> Mapping[str, Any]:
        return {}

    def discover(self, source: str) -> VideoResource:
        normalized = self.normalize(source)
        info = self.client.extract_info(normalized)
        metadata = self._metadata(info, normalized)
        self.cache.save_metadata(metadata)
        return VideoResource(metadata=metadata, subtitles=self._subtitles(info))

    def extract(self, source: str, *, subtitle_language: str | None = None, download_audio: bool = False, download_video: bool = False) -> VideoResource:
        resource = self.discover(source)
        metadata, subtitles = resource.metadata, resource.subtitles
        transcript = self.cache.load_transcript(self.platform, metadata.id) or ()
        transcript_source = "cache" if transcript else None
        if not transcript:
            selected = self.select_subtitle(subtitles, subtitle_language)
            if selected:
                selected = self._download_subtitle(metadata.webpage_url, metadata, selected)
                transcript = SubtitleParser().parse(selected)
                self.cache.save_transcript(metadata, transcript)
                subtitles = (selected,)
                transcript_source = "automatic_subtitle" if selected.is_automatic else "manual_subtitle"
        audio_path = self._download_media(metadata, True) if download_audio else None
        if not transcript and self.transcriber:
            audio_path = audio_path or self._download_media(metadata, True)
            transcript = self.transcriber.transcribe(audio_path, language=subtitle_language)
            self.cache.save_transcript(metadata, transcript)
            transcript_source = "whisper"
        video_path = self._download_media(metadata, False) if download_video else None
        return VideoResource(metadata, subtitles, transcript, audio_path, video_path, transcript_source)

    def select_subtitle(self, subtitles: tuple[Subtitle, ...], preferred: str | None) -> Subtitle | None:
        order = {"vtt": 0, "srt": 1, "ass": 2, "json3": 3}
        candidates = [item for item in subtitles if item.format in order]
        return min(candidates, key=lambda item: (item.is_automatic, 0 if preferred and item.language.casefold() == preferred.casefold() else 1, order[item.format])) if candidates else None

    def _metadata(self, info: Mapping[str, Any], source: str) -> VideoMetadata:
        video_id, title = info.get("id"), info.get("title")
        if not isinstance(video_id, str) or not isinstance(title, str):
            from noteforge.exceptions import RemoteCollectionError
            raise RemoteCollectionError("视频元数据缺少 id 或 title。")
        duration = info.get("duration")
        return VideoMetadata(video_id, title, info.get("uploader") if isinstance(info.get("uploader"), str) else None, int(duration) if isinstance(duration, (int, float)) else None, info.get("thumbnail") if isinstance(info.get("thumbnail"), str) else None, self.platform, info.get("webpage_url") if isinstance(info.get("webpage_url"), str) else source, info.get("description") if isinstance(info.get("description"), str) else None)

    def _subtitles(self, info: Mapping[str, Any]) -> tuple[Subtitle, ...]:
        result: list[Subtitle] = []
        for key, automatic in (("subtitles", False), ("automatic_captions", True)):
            tracks = info.get(key)
            if not isinstance(tracks, Mapping): continue
            for language, formats in tracks.items():
                if not isinstance(language, str) or not isinstance(formats, list): continue
                for item in formats:
                    if isinstance(item, Mapping) and isinstance(item.get("ext"), str):
                        result.append(Subtitle(language, item["ext"].lower(), content=item.get("data") if isinstance(item.get("data"), str) else None, is_automatic=automatic or language.casefold().startswith("ai-")))
        return tuple(result)

    def _download_subtitle(self, source: str, metadata: VideoMetadata, subtitle: Subtitle) -> Subtitle:
        target_dir = self.cache.video_dir(self.platform, metadata.id)
        if subtitle.content is not None:
            path = target_dir / f"subtitle.{subtitle.format}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(subtitle.content, encoding="utf-8")
            return Subtitle(subtitle.language, subtitle.format, path, subtitle.content, subtitle.is_automatic)
        info = self.client.download_subtitle(source, language=subtitle.language, subtitle_format=subtitle.format, target_dir=target_dir)
        requested = info.get("requested_subtitles", {})
        item = requested.get(subtitle.language, {}) if isinstance(requested, Mapping) else {}
        path = item.get("filepath") if isinstance(item, Mapping) else None
        if not isinstance(path, str):
            from noteforge.exceptions import RemoteCollectionError
            raise RemoteCollectionError("yt-dlp 未返回字幕文件路径。")
        return Subtitle(subtitle.language, str(item.get("ext", subtitle.format)), Path(path), is_automatic=subtitle.is_automatic)

    def _download_media(self, metadata: VideoMetadata, audio: bool) -> Path:
        target = self.config.download_path / self.platform / metadata.id / ("audio" if audio else "video")
        info = self.client.download_media(metadata.webpage_url, target_dir=target, audio_only=audio)
        downloads = info.get("requested_downloads")
        path = Path(str(downloads[0].get("filepath", ""))) if isinstance(downloads, list) and downloads else Path(str(info.get("_filename", "")))
        return path.with_suffix(".mp3") if audio else path
