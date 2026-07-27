"""将碎片化的 ``RawChunk`` 转换为适合 LLM 输入的文本块。"""

from dataclasses import dataclass
from math import isfinite
import re
from typing import Iterable

from noteforge.knowledge.chunker import RawChunk


# 只移除含义明确且与讲述内容无关的 ASR 标记，不删除任何口语词。
_ASR_NOISE_MARKERS = ("[音乐]", "[掌声]", "[噪音]")
_ASR_NOISE_PATTERN = re.compile(
    "|".join(re.escape(marker) for marker in _ASR_NOISE_MARKERS)
)


@dataclass(frozen=True, slots=True)
class PreprocessedChunk:
    """规范化后的连续文本块及其原始时间映射。"""

    start_time: float
    end_time: float
    text: str
    source_chunks: tuple[RawChunk, ...]

    def __post_init__(self) -> None:
        if not isfinite(self.start_time) or not isfinite(self.end_time):
            raise ValueError("PreprocessedChunk 的时间必须是有限数值")
        if self.start_time < 0:
            raise ValueError("PreprocessedChunk 的开始时间不能为负数")
        if self.end_time < self.start_time:
            raise ValueError("PreprocessedChunk 的结束时间不能早于开始时间")
        if not self.text.strip():
            raise ValueError("PreprocessedChunk 的文本不能为空")
        if not self.source_chunks:
            raise ValueError("PreprocessedChunk 必须保留至少一个来源文本块")
        if not all(
            isinstance(chunk, RawChunk) for chunk in self.source_chunks
        ):
            raise TypeError("source_chunks 中的元素必须全部是 RawChunk")
        if self.start_time != min(
            chunk.start_time for chunk in self.source_chunks
        ):
            raise ValueError("开始时间必须与来源文本块一致")
        if self.end_time != max(
            chunk.end_time for chunk in self.source_chunks
        ):
            raise ValueError("结束时间必须与来源文本块一致")


class ChunkPreprocessor:
    """执行确定性的文本规范化与相邻块合并。"""

    def __init__(
        self,
        gap_threshold_seconds: float = 0.5,
        max_duration_seconds: float = 120.0,
        max_characters: int = 2000,
    ) -> None:
        if (
            not isfinite(gap_threshold_seconds)
            or gap_threshold_seconds < 0
        ):
            raise ValueError("时间间隔阈值必须是非负有限数值")
        if (
            not isfinite(max_duration_seconds)
            or max_duration_seconds <= 0
        ):
            raise ValueError("最大持续时间必须是正有限数值")
        if (
            isinstance(max_characters, bool)
            or not isinstance(max_characters, int)
            or max_characters <= 0
        ):
            raise ValueError("最大字符数必须是正整数")
        self._gap_threshold_seconds = gap_threshold_seconds
        self._max_duration_seconds = max_duration_seconds
        self._max_characters = max_characters

    @property
    def gap_threshold_seconds(self) -> float:
        """触发相邻文本块合并的最大间隔（秒）。"""

        return self._gap_threshold_seconds

    @property
    def max_duration_seconds(self) -> float:
        """单个预处理块允许的最大持续时间（秒）。"""

        return self._max_duration_seconds

    @property
    def max_characters(self) -> int:
        """单个预处理块允许的最大字符数。"""

        return self._max_characters

    def preprocess(
        self,
        chunks: Iterable[RawChunk],
    ) -> tuple[PreprocessedChunk, ...]:
        """按输入时间顺序预处理一组原始文本块。

        间隔严格小于阈值的块会合并；重叠块的间隔为负，也属于连续块。
        合并结果同时受持续时间和字符数限制。单个 RawChunk 不会被拆分，
        因而它本身超过限制时会作为独立结果保留。
        """

        source_chunks = tuple(chunks)
        if not all(isinstance(chunk, RawChunk) for chunk in source_chunks):
            raise TypeError("chunks 中的元素必须全部是 RawChunk")
        if not source_chunks:
            return ()
        self._validate_time_order(source_chunks)

        groups: list[list[RawChunk]] = []
        normalized_groups: list[list[str]] = []
        current_group = [source_chunks[0]]
        first_text = normalize_text(source_chunks[0].text)
        current_parts = [first_text] if first_text else []
        current_end = source_chunks[0].end_time

        for chunk in source_chunks[1:]:
            normalized_text = normalize_text(chunk.text)
            gap = chunk.start_time - current_end
            if (
                gap < self._gap_threshold_seconds
                and self._can_merge(
                    current_group,
                    current_parts,
                    current_end,
                    chunk,
                    normalized_text,
                )
            ):
                current_group.append(chunk)
                if normalized_text:
                    current_parts.append(normalized_text)
                # 重叠区间可能具有更早的结束时间，合并范围不能因此缩短。
                current_end = max(current_end, chunk.end_time)
                continue

            groups.append(current_group)
            normalized_groups.append(current_parts)
            current_group = [chunk]
            current_parts = [normalized_text] if normalized_text else []
            current_end = chunk.end_time
        groups.append(current_group)
        normalized_groups.append(current_parts)

        results: list[PreprocessedChunk] = []
        for group, normalized_parts in zip(
            groups,
            normalized_groups,
            strict=True,
        ):
            if not normalized_parts:
                continue
            results.append(
                PreprocessedChunk(
                    start_time=group[0].start_time,
                    end_time=max(chunk.end_time for chunk in group),
                    text="\n".join(normalized_parts),
                    source_chunks=tuple(group),
                )
            )
        return tuple(results)

    @staticmethod
    def _validate_time_order(chunks: tuple[RawChunk, ...]) -> None:
        """拒绝乱序输入，避免静默隐藏上游数据问题。"""

        for previous, current in zip(chunks, chunks[1:]):
            if current.start_time < previous.start_time:
                raise ValueError(
                    "RawChunk 必须按 start_time 非递减顺序输入"
                )

    def _can_merge(
        self,
        current_group: list[RawChunk],
        current_parts: list[str],
        current_end: float,
        next_chunk: RawChunk,
        next_text: str,
    ) -> bool:
        """判断加入下一个原始块后是否仍满足输入规模限制。"""

        merged_end = max(current_end, next_chunk.end_time)
        merged_duration = merged_end - current_group[0].start_time
        if merged_duration > self._max_duration_seconds:
            return False

        current_characters = sum(len(part) for part in current_parts)
        current_characters += max(0, len(current_parts) - 1)
        separator_length = 1 if current_parts and next_text else 0
        merged_characters = (
            current_characters + separator_length + len(next_text)
        )
        return merged_characters <= self._max_characters


def normalize_text(text: str) -> str:
    """移除明确 ASR 噪声并统一空白，不改写其余文本。"""

    if not isinstance(text, str):
        raise TypeError("text 必须是字符串")
    without_noise = _ASR_NOISE_PATTERN.sub(" ", text)
    return " ".join(without_noise.split())


def preprocess_raw_chunks(
    chunks: Iterable[RawChunk],
    *,
    gap_threshold_seconds: float = 0.5,
    max_duration_seconds: float = 120.0,
    max_characters: int = 2000,
) -> tuple[PreprocessedChunk, ...]:
    """使用给定的合并策略预处理原始文本块。"""

    return ChunkPreprocessor(
        gap_threshold_seconds=gap_threshold_seconds,
        max_duration_seconds=max_duration_seconds,
        max_characters=max_characters,
    ).preprocess(chunks)
