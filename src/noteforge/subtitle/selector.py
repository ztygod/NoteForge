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
DEFAULT_FORMAT_PRIORITY = ("vtt", "srt", "json3", "ttml")


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
        format_fallback = len(format_rank)

        return min(
            tracks,
            key=lambda track: (
                language_rank.get(
                    track.language.casefold(),
                    language_fallback,
                ),
                track.is_automatic,
                format_rank.get(
                    track.extension.casefold(),
                    format_fallback,
                ),
            ),
        )
