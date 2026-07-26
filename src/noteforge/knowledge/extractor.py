"""负责TranscriptSegment到RawChunk的转换。"""

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from noteforge.subtitle.models import Transcript, TranscriptSegment


@dataclass(frozen=True, slots=True)
class RawChunk:
    """可供知识抽取器消费的原始文本块。

    ``RawChunk`` 当前与字幕片段一一对应。这里不合并相邻字幕，以免在没有
    明确分块策略的情况下丢失时间边界；后续需要按长度或语义合并时，可以
    在转换之后单独增加策略。
    """

    start_time: float
    end_time: float
    text: str

    def __post_init__(self) -> None:
        """保证进入后续处理流程的数据具有有效的时间范围和文本。"""

        if not isfinite(self.start_time) or not isfinite(self.end_time):
            raise ValueError("RawChunk 的时间必须是有限数值。")
        if self.start_time < 0:
            raise ValueError("RawChunk 的开始时间不能为负数。")
        if self.end_time < self.start_time:
            raise ValueError("RawChunk 的结束时间不能早于开始时间。")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("RawChunk 的文本不能为空。")

    @property
    def duration(self) -> float:
        """文本块持续时长（秒）。"""

        return self.end_time - self.start_time

    @classmethod
    def from_segment(cls, segment: TranscriptSegment) -> "RawChunk":
        """从一个字幕片段创建原始文本块。"""

        if not isinstance(segment, TranscriptSegment):
            raise TypeError("segment 必须是 TranscriptSegment。")
        return cls(
            start_time=segment.start_seconds,
            end_time=segment.end_seconds,
            text=segment.text,
        )


class TranscriptChunker:
    """按字幕中的原有顺序生成原始文本块。"""

    def chunk_segment(self, segment: TranscriptSegment) -> RawChunk:
        """转换单个字幕片段。"""

        return RawChunk.from_segment(segment)

    def chunk_segments(
        self,
        segments: Iterable[TranscriptSegment],
    ) -> tuple[RawChunk, ...]:
        """按输入顺序转换一组字幕片段。"""

        return tuple(self.chunk_segment(segment) for segment in segments)

    def chunk(self, transcript: Transcript) -> tuple[RawChunk, ...]:
        """转换一份完整字幕。"""

        if not isinstance(transcript, Transcript):
            raise TypeError("transcript 必须是 Transcript。")
        return self.chunk_segments(transcript.segments)


def segment_to_raw_chunk(segment: TranscriptSegment) -> RawChunk:
    """便捷函数：转换单个字幕片段。"""

    return RawChunk.from_segment(segment)


def transcript_to_raw_chunks(transcript: Transcript) -> tuple[RawChunk, ...]:
    """便捷函数：转换一份完整字幕。"""

    return TranscriptChunker().chunk(transcript)
