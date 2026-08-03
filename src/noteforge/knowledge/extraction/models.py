"""知识点提取层的数据模型。"""

from dataclasses import dataclass
from math import isfinite

from noteforge.knowledge.semantic.models import SemanticChunk
from noteforge.knowledge.taxonomy import KnowledgePointType


@dataclass(frozen=True, slots=True)
class KnowledgePoint:
    """从语义块中提取出的独立知识单元。"""

    title: str
    explanation: str
    point_type: KnowledgePointType
    keywords: tuple[str, ...]
    importance: float
    source_chunks: tuple[SemanticChunk, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("KnowledgePoint 的标题不能为空")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("KnowledgePoint 的解释不能为空")
        if not isinstance(self.point_type, KnowledgePointType):
            raise TypeError("KnowledgePoint 的 point_type 必须是合法枚举值")
        if (
            isinstance(self.importance, bool)
            or not isinstance(self.importance, (int, float))
            or not isfinite(self.importance)
            or not 0 <= self.importance <= 1
        ):
            raise ValueError("KnowledgePoint 的 importance 必须位于 [0, 1]")
        if not self.source_chunks:
            raise ValueError("KnowledgePoint 必须保留至少一个来源块")
        if not all(
            isinstance(chunk, SemanticChunk) for chunk in self.source_chunks
        ):
            raise TypeError(
                "KnowledgePoint 的 source_chunks 必须全部是 SemanticChunk"
            )
        if any(
            current.start_time < previous.start_time
            or current.end_time < previous.end_time
            for previous, current in zip(
                self.source_chunks,
                self.source_chunks[1:],
            )
        ):
            raise ValueError("KnowledgePoint 的 source_chunks 时间顺序不能倒序")

        seen: set[str] = set()
        for keyword in self.keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("KnowledgePoint 的 keywords 不能包含空字符串")
            if keyword != keyword.strip():
                raise ValueError("KnowledgePoint 的 keywords 必须去除首尾空白")
            if keyword in seen:
                raise ValueError("KnowledgePoint 的 keywords 不能重复")
            seen.add(keyword)

    @property
    def start_time(self) -> float:
        """知识点首个来源块的开始时间。"""

        return self.source_chunks[0].start_time

    @property
    def end_time(self) -> float:
        """知识点末个来源块的结束时间。"""

        return self.source_chunks[-1].end_time


@dataclass(frozen=True, slots=True)
class KnowledgePointProposal:
    """LLM 返回的知识点提案，不包含来源对象或时间。"""

    source_indexes: tuple[int, ...]
    title: str
    explanation: str
    point_type: KnowledgePointType
    keywords: tuple[str, ...]
    importance: float


@dataclass(frozen=True, slots=True)
class KnowledgeExtractionResult:
    """一批语义块对应的知识点提取结果。"""

    knowledge_points: tuple[KnowledgePointProposal, ...]
