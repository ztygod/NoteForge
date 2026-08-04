"""字幕轨道选择策略。"""

from noteforge.collector.models import SubtitleTrack

DEFAULT_LANGUAGE_PRIORITY = (
    "zh-Hans",
    "zh-CN",
    "zh",
    "ai-zh",
    "zh-Hant",
    "en",
    "en-US",
)
# 当前解析器只支持 VTT 和 SRT。这里既是优先级，也是 selector 的
# 可选格式白名单，避免把 B 站弹幕 XML 当成字幕。
DEFAULT_FORMAT_PRIORITY = ("vtt", "srt")


class SubtitleSelector:
    """按语言、人工/自动类型和格式优先级选择字幕。"""

    def __init__(
        self,
        preferred_languages: tuple[str, ...] = DEFAULT_LANGUAGE_PRIORITY,
        preferred_formats: tuple[str, ...] = DEFAULT_FORMAT_PRIORITY,
    ) -> None:
        self._preferred_languages = preferred_languages
        self._preferred_formats = preferred_formats

    def select(
        self,
        tracks: tuple[SubtitleTrack, ...],
    ) -> SubtitleTrack | None:
        if not tracks:
            return None

        language_rank = {
            language.casefold(): index
            for index, language in enumerate(self._preferred_languages)
        }
        format_rank = {
            extension.casefold(): index
            for index, extension in enumerate(self._preferred_formats)
        }
        language_fallback = len(language_rank)
        supported_tracks = tuple(
            track
            for track in tracks
            if track.extension.casefold() in format_rank
        )
        if not supported_tracks:
            return None

        return min(
            supported_tracks,
            key=lambda track: (
                language_rank.get(
                    track.language.casefold(),
                    language_fallback,
                ),
                track.is_automatic,
                format_rank[track.extension.casefold()],
            ),
        )
