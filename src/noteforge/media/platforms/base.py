"""平台差异适配器。"""

from abc import ABC
from collections.abc import Mapping
from typing import Any

from noteforge.exceptions import RemoteCollectionError, UnsupportedSourceError
from noteforge.media.models import (
    AudioFormat,
    MediaFormats,
    Playlist,
    PlaylistEntry,
    Subtitle,
    VideoFormat,
    VideoMetadata,
    VideoPlatform,
)
from noteforge.media.source import InspectionPlatform, inspect_source


class PlatformAdapter(ABC):
    """把平台/yt-dlp 原始结构转换为稳定领域对象。"""

    platform: VideoPlatform  # 子类必须声明唯一平台。

    def supports(self, source: str) -> bool:
        """通过本地 URL 检查判断支持性，不发起网络请求。"""

        return inspect_source(source).platform.value == self.platform.value

    def normalize(self, source: str) -> str:
        """移除无关查询参数并生成稳定平台 URL。"""

        result = inspect_source(source)
        expected = InspectionPlatform(self.platform.value)
        if result.platform is not expected or result.normalized_source is None:
            raise UnsupportedSourceError(
                f"不支持的 {self.platform.value} URL：{source}"
            )
        return result.normalized_source

    def backend_options(self) -> Mapping[str, Any]:
        """返回平台必需的内部后端选项，不向调用方开放。"""

        return {}

    def metadata(self, info: Mapping[str, Any], source: str) -> VideoMetadata:
        """校验并映射平台元数据。"""

        video_id, title = info.get("id"), info.get("title")
        if not isinstance(video_id, str) or not isinstance(title, str):
            raise RemoteCollectionError("视频元数据缺少 id 或 title。")

        uploader = info.get("uploader")
        duration = info.get("duration")
        thumbnail = info.get("thumbnail")
        webpage_url = info.get("webpage_url")
        description = info.get("description")
        return VideoMetadata(
            id=video_id,
            title=title,
            uploader=uploader if isinstance(uploader, str) else None,
            duration=int(duration) if isinstance(duration, (int, float)) else None,
            thumbnail=thumbnail if isinstance(thumbnail, str) else None,
            platform=self.platform.value,
            webpage_url=webpage_url if isinstance(webpage_url, str) else source,
            description=description if isinstance(description, str) else None,
        )

    def subtitles(self, info: Mapping[str, Any]) -> tuple[Subtitle, ...]:
        """合并人工与自动字幕描述。"""

        result: list[Subtitle] = []
        for key, automatic in (("subtitles", False), ("automatic_captions", True)):
            tracks = info.get(key)
            if not isinstance(tracks, Mapping):
                continue
            for language, formats in tracks.items():
                if not isinstance(language, str) or not isinstance(formats, list):
                    continue
                for item in formats:
                    if isinstance(item, Mapping) and isinstance(item.get("ext"), str):
                        result.append(
                            Subtitle(
                                language,
                                item["ext"].lower(),
                                content=item.get("data")
                                if isinstance(item.get("data"), str)
                                else None,
                                is_automatic=automatic
                                or language.casefold().startswith("ai-"),
                            )
                        )
        return tuple(result)

    def formats(self, info: Mapping[str, Any]) -> MediaFormats:
        """把混合格式列表拆成标准化视频与音频集合。"""

        videos: list[VideoFormat] = []
        audios: list[AudioFormat] = []
        raw = info.get("formats")
        if not isinstance(raw, list):
            return MediaFormats()
        for item in raw:
            if not isinstance(item, Mapping) or not isinstance(
                item.get("format_id"), str
            ):
                continue
            size = item.get("filesize") or item.get("filesize_approx")
            common_size = int(size) if isinstance(size, (int, float)) else None
            if item.get("vcodec") not in {None, "none"}:
                videos.append(
                    VideoFormat(
                        item["format_id"],
                        item.get("ext") if isinstance(item.get("ext"), str) else None,
                        int(item["width"])
                        if isinstance(item.get("width"), (int, float))
                        else None,
                        int(item["height"])
                        if isinstance(item.get("height"), (int, float))
                        else None,
                        float(item["fps"])
                        if isinstance(item.get("fps"), (int, float))
                        else None,
                        item.get("vcodec")
                        if isinstance(item.get("vcodec"), str)
                        else None,
                        item.get("acodec")
                        if isinstance(item.get("acodec"), str)
                        else None,
                        float(item["tbr"])
                        if isinstance(item.get("tbr"), (int, float))
                        else None,
                        common_size,
                    )
                )
            if item.get("acodec") not in {None, "none"}:
                audios.append(
                    AudioFormat(
                        item["format_id"],
                        item.get("ext") if isinstance(item.get("ext"), str) else None,
                        item.get("acodec")
                        if isinstance(item.get("acodec"), str)
                        else None,
                        float(item["abr"])
                        if isinstance(item.get("abr"), (int, float))
                        else None,
                        int(item["asr"])
                        if isinstance(item.get("asr"), (int, float))
                        else None,
                        common_size,
                    )
                )
        return MediaFormats(tuple(videos), tuple(audios))

    def playlist(self, info: Mapping[str, Any], source: str) -> Playlist:
        """映射轻量播放列表；忽略缺少 ID 或 URL 的无效条目。"""

        entries = info.get("entries")
        if not isinstance(entries, list):
            raise RemoteCollectionError("该来源不是播放列表。")
        mapped: list[PlaylistEntry] = []
        for index, item in enumerate(entries, 1):
            if not isinstance(item, Mapping):
                continue
            entry_id = item.get("id")
            url = item.get("webpage_url") or item.get("url")
            if isinstance(entry_id, str) and isinstance(url, str):
                mapped.append(
                    PlaylistEntry(
                        entry_id,
                        item.get("title")
                        if isinstance(item.get("title"), str)
                        else None,
                        url,
                        index,
                    )
                )
        return Playlist(
            str(info.get("id", source)),
            str(info.get("title", "Playlist")),
            tuple(mapped),
        )
