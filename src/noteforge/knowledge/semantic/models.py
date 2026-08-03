"""语义切分的数据模型。"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from noteforge.knowledge.preprocessor import PreprocessedChunk


class SemanticChunkType(StrEnum):
    """语义块的内容类型。"""

    DEFINITION = "definition"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    COMPARISON = "comparison"
    PROCEDURE = "procedure"
    CONCLUSION = "conclusion"
    TRANSITION = "transition"
    QUESTION = "question"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SemanticChunk:
    """经过语义分析后形成的连续知识块。"""

    start_time: float
    end_time: float
    text: str
    topic: str
    summary: str
    chunk_type: SemanticChunkType
    importance: float
    source_chunks: tuple[PreprocessedChunk, ...]

    def __post_init__(self) -> None:
        if not isfinite(self.start_time) or not isfinite(self.end_time):
            raise ValueError("SemanticChunk 的时间必须是有限数值")
        if self.start_time < 0:
            raise ValueError("SemanticChunk 的开始时间不能为负数")
        if self.end_time < self.start_time:
            raise ValueError("SemanticChunk 的结束时间不能早于开始时间")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("SemanticChunk 的文本不能为空")
        if not isinstance(self.topic, str) or not self.topic.strip():
            raise ValueError("SemanticChunk 的主题不能为空")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("SemanticChunk 的摘要不能为空")
        if not isinstance(self.chunk_type, SemanticChunkType):
            raise TypeError("SemanticChunk 的 chunk_type 必须是合法枚举值")
        if (
            isinstance(self.importance, bool)
            or not isinstance(self.importance, (int, float))
            or not isfinite(self.importance)
            or not 0 <= self.importance <= 1
        ):
            raise ValueError("SemanticChunk 的 importance 必须位于 [0, 1]")
        if not self.source_chunks:
            raise ValueError("SemanticChunk 必须保留至少一个来源块")
        if not all(
            isinstance(chunk, PreprocessedChunk)
            for chunk in self.source_chunks
        ):
            raise TypeError(
                "SemanticChunk 的 source_chunks 必须全部是 PreprocessedChunk"
            )
        if self.start_time != self.source_chunks[0].start_time:
            raise ValueError("SemanticChunk 的开始时间必须与首个来源块一致")
        if self.end_time != self.source_chunks[-1].end_time:
            raise ValueError("SemanticChunk 的结束时间必须与末个来源块一致")


@dataclass(frozen=True, slots=True)
class SemanticChunkProposal:
    """模型对一个语义块的判断，不包含可由程序确定的数据。"""

    source_indexes: tuple[int, ...]
    topic: str
    summary: str
    chunk_type: SemanticChunkType
    importance: float


@dataclass(frozen=True, slots=True)
class SemanticAnalysisResult:
    """一批输入对应的模型语义分析结果。"""

    semantic_chunks: tuple[SemanticChunkProposal, ...]
