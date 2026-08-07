"""将 VTT、SRT、ASS 和 YouTube JSON3 统一解析为带时间戳的字幕片段。"""

from html import unescape
import json
import re

from noteforge.exceptions import SubtitleParseError
from noteforge.media.models import Subtitle, SubtitleSegment

_TAG = re.compile(r"<[^>]+>")
_ASS_TAG = re.compile(r"\{[^}]*\}")


class SubtitleParser:
    def parse(self, subtitle: Subtitle) -> tuple[SubtitleSegment, ...]:
        content = subtitle.content
        if content is None and subtitle.path is not None:
            try:
                content = subtitle.path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as error:
                raise SubtitleParseError(f"无法读取字幕：{subtitle.path}") from error
        if content is None:
            raise SubtitleParseError("字幕既没有正文也没有文件路径。")
        fmt = subtitle.format.casefold().lstrip(".")
        if fmt in {"vtt", "srt"}:
            segments = self._timed_text(content, fmt)
        elif fmt == "ass":
            segments = self._ass(content)
        elif fmt == "json3":
            segments = self._json3(content)
        else:
            raise SubtitleParseError(f"当前不支持字幕格式：{subtitle.format}")
        return self.normalize(segments)

    @staticmethod
    def normalize(
        segments: tuple[SubtitleSegment, ...],
    ) -> tuple[SubtitleSegment, ...]:
        """统一空白并删除文本完全相同的连续字幕。"""

        normalized: list[SubtitleSegment] = []
        for segment in segments:
            text = " ".join(segment.text.split())
            if not text or normalized and normalized[-1].text == text:
                continue
            normalized.append(SubtitleSegment(segment.start, segment.end, text))
        return tuple(normalized)

    def _timed_text(self, content: str, fmt: str) -> tuple[SubtitleSegment, ...]:
        segments: list[SubtitleSegment] = []
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        for block in re.split(r"\n[ \t]*\n", normalized):
            lines = [line.strip() for line in block.splitlines()]
            timing = next((line for line in lines if "-->" in line), None)
            if timing is None:
                continue
            index = lines.index(timing)
            parts = timing.split("-->", 1)
            try:
                start = self._timestamp(parts[0].strip(), fmt)
                end = self._timestamp(parts[1].strip().split()[0], fmt)
            except (ValueError, IndexError) as error:
                raise SubtitleParseError(f"无效的 {fmt.upper()} 时间行：{timing}") from error
            text = "\n".join(unescape(_TAG.sub("", line)) for line in lines[index + 1:]).strip()
            if text:
                segments.append(SubtitleSegment(start, end, text))
        return tuple(segments)

    @staticmethod
    def _timestamp(value: str, fmt: str) -> float:
        value = value.replace(",", ".") if fmt == "srt" else value
        pieces = value.split(":")
        if len(pieces) == 2:
            hours, minutes, seconds = 0, int(pieces[0]), float(pieces[1])
        elif len(pieces) == 3:
            hours, minutes, seconds = int(pieces[0]), int(pieces[1]), float(pieces[2])
        else:
            raise ValueError(value)
        if minutes >= 60 or seconds >= 60:
            raise ValueError(value)
        return hours * 3600 + minutes * 60 + seconds

    def _ass(self, content: str) -> tuple[SubtitleSegment, ...]:
        segments: list[SubtitleSegment] = []
        for line in content.splitlines():
            if not line.lstrip().casefold().startswith("dialogue:"):
                continue
            fields = line.split(":", 1)[1].split(",", 9)
            if len(fields) != 10:
                continue
            try:
                start, end = self._timestamp(fields[1].strip(), "vtt"), self._timestamp(fields[2].strip(), "vtt")
            except ValueError:
                continue
            text = unescape(_ASS_TAG.sub("", fields[9])).replace(r"\N", "\n").strip()
            if text:
                segments.append(SubtitleSegment(start, end, text))
        return tuple(segments)

    @staticmethod
    def _json3(content: str) -> tuple[SubtitleSegment, ...]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise SubtitleParseError("JSON3 字幕不是有效 JSON。") from error
        segments: list[SubtitleSegment] = []
        for event in payload.get("events", []) if isinstance(payload, dict) else []:
            if not isinstance(event, dict) or "tStartMs" not in event:
                continue
            text = "".join(
                part.get("utf8", "") for part in event.get("segs", [])
                if isinstance(part, dict)
            ).strip()
            if text:
                start = float(event["tStartMs"]) / 1000
                end = start + float(event.get("dDurationMs", 0)) / 1000
                segments.append(SubtitleSegment(start, end, text))
        return tuple(segments)
