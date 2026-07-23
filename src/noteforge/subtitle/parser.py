"""字幕文件解析器。"""

from abc import ABC, abstractmethod
from html import unescape
import re

from noteforge.exceptions import SubtitleParseError
from noteforge.subtitle.models import (
    SubtitleFile,
    Transcript,
    TranscriptSegment,
)

_TIMING_LINE = re.compile(r"^(\S+)\s+-->\s+(\S+)(?:\s+.*)?$")
_VTT_TIMESTAMP = re.compile(
    r"^(?:(?P<hours>\d+):)?"
    r"(?P<minutes>\d{2}):"
    r"(?P<seconds>\d{2})\."
    r"(?P<milliseconds>\d{3})$"
)
_SRT_TIMESTAMP = re.compile(
    r"^(?P<hours>\d+):"
    r"(?P<minutes>\d{2}):"
    r"(?P<seconds>\d{2}),"
    r"(?P<milliseconds>\d{3})$"
)
_SUBTITLE_TAG = re.compile(r"<[^>]+>")


class SubtitleParser(ABC):
    """字幕文件解析器的统一接口。"""

    @abstractmethod
    def parse(self, subtitle: SubtitleFile) -> Transcript:
        """把字幕文件转换为结构化 Transcript。"""


def _parse_timestamp(
    value: str,
    pattern: re.Pattern[str],
    format_name: str,
) -> float:
    match = pattern.fullmatch(value)
    if match is None:
        raise SubtitleParseError(f"无效的 {format_name} 时间戳：{value}")

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = int(match.group("milliseconds"))
    if minutes >= 60 or seconds >= 60:
        raise SubtitleParseError(f"无效的 {format_name} 时间戳：{value}")

    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def _read_subtitle(subtitle: SubtitleFile, format_name: str) -> str:
    try:
        return subtitle.path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise SubtitleParseError(
            f"无法读取 {format_name} 字幕文件：{subtitle.path}"
        ) from error


def _transcript_source(subtitle: SubtitleFile) -> str:
    return (
        "automatic_subtitle"
        if subtitle.is_automatic
        else "manual_subtitle"
    )


class VttSubtitleParser(SubtitleParser):
    """解析 WebVTT 字幕。"""

    def parse(self, subtitle: SubtitleFile) -> Transcript:
        if subtitle.extension.casefold() != "vtt":
            raise SubtitleParseError(
                f"当前只支持 VTT 字幕，收到：{subtitle.extension}"
            )

        content = _read_subtitle(subtitle, "VTT")

        normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
        blocks = re.split(r"\n[ \t]*\n", normalized_content)
        segments: list[TranscriptSegment] = []

        for block in blocks:
            lines = [line.strip() for line in block.splitlines()]
            if not lines:
                continue
            if lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                continue

            timing_index = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if "-->" in line
                ),
                None,
            )
            if timing_index is None:
                continue

            timing_match = _TIMING_LINE.fullmatch(lines[timing_index])
            if timing_match is None:
                raise SubtitleParseError(
                    f"无效的 VTT 时间行：{lines[timing_index]}"
                )

            start_seconds = _parse_timestamp(
                timing_match.group(1),
                _VTT_TIMESTAMP,
                "VTT",
            )
            end_seconds = _parse_timestamp(
                timing_match.group(2),
                _VTT_TIMESTAMP,
                "VTT",
            )
            if end_seconds < start_seconds:
                raise SubtitleParseError("VTT 字幕结束时间早于开始时间。")

            text_lines = lines[timing_index + 1 :]
            text = "\n".join(
                unescape(_SUBTITLE_TAG.sub("", line))
                for line in text_lines
            ).strip()
            if not text:
                continue

            segments.append(
                TranscriptSegment(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    text=text,
                )
            )

        return Transcript(
            language=subtitle.language,
            segments=tuple(segments),
            source=_transcript_source(subtitle),
        )


class SrtSubtitleParser(SubtitleParser):
    """解析 SubRip 字幕。"""

    def parse(self, subtitle: SubtitleFile) -> Transcript:
        if subtitle.extension.casefold() != "srt":
            raise SubtitleParseError(
                f"SRT 解析器不支持该字幕格式：{subtitle.extension}"
            )

        content = _read_subtitle(subtitle, "SRT")
        normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
        blocks = re.split(r"\n[ \t]*\n", normalized_content)
        segments: list[TranscriptSegment] = []

        for block in blocks:
            lines = [line.strip() for line in block.splitlines()]
            if not lines:
                continue

            timing_index = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if "-->" in line
                ),
                None,
            )
            if timing_index is None:
                continue

            timing_match = _TIMING_LINE.fullmatch(lines[timing_index])
            if timing_match is None:
                raise SubtitleParseError(
                    f"无效的 SRT 时间行：{lines[timing_index]}"
                )

            start_seconds = _parse_timestamp(
                timing_match.group(1),
                _SRT_TIMESTAMP,
                "SRT",
            )
            end_seconds = _parse_timestamp(
                timing_match.group(2),
                _SRT_TIMESTAMP,
                "SRT",
            )
            if end_seconds < start_seconds:
                raise SubtitleParseError("SRT 字幕结束时间早于开始时间。")

            text = "\n".join(
                unescape(_SUBTITLE_TAG.sub("", line))
                for line in lines[timing_index + 1 :]
            ).strip()
            if not text:
                continue

            segments.append(
                TranscriptSegment(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    text=text,
                )
            )

        return Transcript(
            language=subtitle.language,
            segments=tuple(segments),
            source=_transcript_source(subtitle),
        )


def parse_subtitle(subtitle: SubtitleFile) -> Transcript:
    """按文件扩展名选择已支持的字幕解析器。"""

    extension = subtitle.extension.casefold()
    if extension == "vtt":
        return VttSubtitleParser().parse(subtitle)
    if extension == "srt":
        return SrtSubtitleParser().parse(subtitle)
    raise SubtitleParseError(f"当前不支持字幕格式：{subtitle.extension}")
