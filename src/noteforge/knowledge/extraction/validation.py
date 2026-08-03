"""知识点模型输出的解析与严格校验。"""

from math import isfinite
from typing import Any

from noteforge.exceptions import KnowledgeExtractionError
from noteforge.knowledge.extraction.models import (
    KnowledgeExtractionResult,
    KnowledgePointProposal,
    KnowledgePointType,
)


_PROPOSAL_FIELDS = {
    "source_indexes",
    "title",
    "explanation",
    "point_type",
    "keywords",
    "importance",
}

# 模型偶尔会沿用上游 SemanticChunkType。这里只收敛含义明确的近义类型；
# 其他未知值继续拒绝，避免把真实的模型错误静默写进文档。
_POINT_TYPE_ALIASES = {
    "definition": KnowledgePointType.CONCEPT,
    "explanation": KnowledgePointType.CONCEPT,
    "question": KnowledgePointType.OTHER,
    "transition": KnowledgePointType.OTHER,
}


def parse_knowledge_extraction_result(
    value: object,
) -> KnowledgeExtractionResult:
    """将 LLM JSON 解析为提案模型，并拒绝额外或缺失字段。"""

    if not isinstance(value, dict):
        raise KnowledgeExtractionError(
            "Knowledge extraction result must be a JSON object"
        )
    if set(value) != {"knowledge_points"}:
        raise KnowledgeExtractionError(
            "Knowledge extraction result must contain only knowledge_points"
        )
    raw_points = value["knowledge_points"]
    if not isinstance(raw_points, list):
        raise KnowledgeExtractionError(
            "Knowledge extraction result knowledge_points must be an array"
        )
    return KnowledgeExtractionResult(
        tuple(
            _parse_proposal(raw_point, position)
            for position, raw_point in enumerate(raw_points)
        )
    )


def _parse_proposal(value: Any, position: int) -> KnowledgePointProposal:
    prefix = f"Knowledge point {position}"
    if not isinstance(value, dict):
        raise KnowledgeExtractionError(f"{prefix} must be a JSON object")
    if set(value) != _PROPOSAL_FIELDS:
        missing = sorted(_PROPOSAL_FIELDS.difference(value))
        extra = sorted(set(value).difference(_PROPOSAL_FIELDS))
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected fields: {', '.join(extra)}")
        raise KnowledgeExtractionError(f"{prefix} has " + "; ".join(details))

    indexes = value["source_indexes"]
    if not isinstance(indexes, list):
        raise KnowledgeExtractionError(
            f"{prefix} source_indexes must be an array"
        )
    keywords = value["keywords"]
    if not isinstance(keywords, list) or any(
        not isinstance(keyword, str) for keyword in keywords
    ):
        raise KnowledgeExtractionError(
            f"{prefix} keywords must be an array of strings"
        )
    raw_point_type = value["point_type"]
    try:
        point_type = KnowledgePointType(raw_point_type)
    except (TypeError, ValueError) as error:
        point_type = (
            _POINT_TYPE_ALIASES.get(raw_point_type)
            if isinstance(raw_point_type, str)
            else None
        )
        if point_type is None:
            raise KnowledgeExtractionError(
                f"{prefix} contains invalid point_type: {raw_point_type!r}"
            ) from error
    return KnowledgePointProposal(
        source_indexes=tuple(indexes),
        title=value["title"],
        explanation=value["explanation"],
        point_type=point_type,
        keywords=tuple(keywords),
        importance=value["importance"],
    )


def validate_knowledge_proposals(
    proposals: tuple[KnowledgePointProposal, ...],
    source_count: int,
) -> None:
    """校验提案字段；不同提案之间允许复用来源索引。"""

    if (
        isinstance(source_count, bool)
        or not isinstance(source_count, int)
        or source_count < 0
    ):
        raise ValueError("source_count 必须是非负整数")
    for position, proposal in enumerate(proposals):
        prefix = f"Knowledge point {position}"
        indexes = proposal.source_indexes
        if not indexes:
            raise KnowledgeExtractionError(
                f"{prefix} contains empty source_indexes"
            )
        seen_indexes: set[int] = set()
        for index in indexes:
            if isinstance(index, bool) or not isinstance(index, int):
                raise KnowledgeExtractionError(
                    f"{prefix} contains non-integer source index: {index!r}"
                )
            if index < 0 or index >= source_count:
                raise KnowledgeExtractionError(
                    f"{prefix} contains out-of-range source index: {index}"
                )
            if index in seen_indexes:
                raise KnowledgeExtractionError(
                    f"{prefix} contains duplicated source index: {index}"
                )
            seen_indexes.add(index)
        if any(right <= left for left, right in zip(indexes, indexes[1:])):
            raise KnowledgeExtractionError(
                f"{prefix} contains non-increasing source indexes: {indexes}"
            )
        if any(right != left + 1 for left, right in zip(indexes, indexes[1:])):
            raise KnowledgeExtractionError(
                f"{prefix} contains non-contiguous source indexes: {indexes}"
            )
        if not isinstance(proposal.title, str) or not proposal.title.strip():
            raise KnowledgeExtractionError(f"{prefix} title must not be empty")
        if (
            not isinstance(proposal.explanation, str)
            or not proposal.explanation.strip()
        ):
            raise KnowledgeExtractionError(
                f"{prefix} explanation must not be empty"
            )
        if not isinstance(proposal.point_type, KnowledgePointType):
            raise KnowledgeExtractionError(
                f"{prefix} contains invalid point_type: "
                f"{proposal.point_type!r}"
            )
        if (
            isinstance(proposal.importance, bool)
            or not isinstance(proposal.importance, (int, float))
            or not isfinite(proposal.importance)
            or not 0 <= proposal.importance <= 1
        ):
            raise KnowledgeExtractionError(
                f"{prefix} importance must be between 0 and 1"
            )

        normalized_keywords: set[str] = set()
        if not 1 <= len(proposal.keywords) <= 6:
            raise KnowledgeExtractionError(
                f"{prefix} keywords must contain between 1 and 6 values"
            )
        for keyword in proposal.keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise KnowledgeExtractionError(
                    f"{prefix} keywords must not contain empty values"
                )
            cleaned = keyword.strip()
            if cleaned in normalized_keywords:
                raise KnowledgeExtractionError(
                    f"{prefix} contains duplicated keyword: {cleaned!r}"
                )
            normalized_keywords.add(cleaned)
