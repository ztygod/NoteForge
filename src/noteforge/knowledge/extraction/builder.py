"""从模型提案确定性地构造知识点。"""

from noteforge.knowledge.extraction.models import (
    KnowledgePoint,
    KnowledgePointProposal,
)
from noteforge.knowledge.semantic.models import SemanticChunk


def normalize_keywords(keywords: tuple[str, ...]) -> tuple[str, ...]:
    """清理空白，并在保持顺序的前提下删除空值和重复值。"""

    normalized: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        cleaned = keyword.strip()
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return tuple(normalized)


def build_knowledge_point(
    chunks: tuple[SemanticChunk, ...],
    proposal: KnowledgePointProposal,
) -> KnowledgePoint:
    """根据索引获取真实来源，模型不能提供或修改来源信息。"""

    source_chunks = tuple(chunks[index] for index in proposal.source_indexes)
    return KnowledgePoint(
        title=proposal.title.strip(),
        explanation=proposal.explanation.strip(),
        point_type=proposal.point_type,
        keywords=normalize_keywords(proposal.keywords),
        importance=proposal.importance,
        source_chunks=source_chunks,
    )
