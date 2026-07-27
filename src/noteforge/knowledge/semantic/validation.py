"""模型语义分析结果的严格校验与解析。"""

from math import isfinite
from typing import Any

from noteforge.exceptions import SemanticAnalysisError
from noteforge.knowledge.semantic.models import (
    SemanticAnalysisResult,
    SemanticChunkProposal,
    SemanticChunkType,
)


_PROPOSAL_FIELDS = {
    "source_indexes",
    "topic",
    "summary",
    "chunk_type",
    "importance",
}


def parse_semantic_analysis_result(value: object) -> SemanticAnalysisResult:
    """将 LLM JSON 转换为独立模型，并拒绝结构或字段错误。"""

    if not isinstance(value, dict):
        raise SemanticAnalysisError(
            "Semantic analysis result must be a JSON object"
        )
    if set(value) != {"semantic_chunks"}:
        raise SemanticAnalysisError(
            "Semantic analysis result must contain only semantic_chunks"
        )
    raw_proposals = value["semantic_chunks"]
    if not isinstance(raw_proposals, list):
        raise SemanticAnalysisError(
            "Semantic analysis result semantic_chunks must be an array"
        )

    proposals: list[SemanticChunkProposal] = []
    for position, raw_proposal in enumerate(raw_proposals):
        proposals.append(_parse_proposal(raw_proposal, position))
    return SemanticAnalysisResult(tuple(proposals))


def _parse_proposal(value: Any, position: int) -> SemanticChunkProposal:
    prefix = f"Semantic analysis proposal {position}"
    if not isinstance(value, dict):
        raise SemanticAnalysisError(f"{prefix} must be a JSON object")
    if set(value) != _PROPOSAL_FIELDS:
        missing = sorted(_PROPOSAL_FIELDS.difference(value))
        extra = sorted(set(value).difference(_PROPOSAL_FIELDS))
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected fields: {', '.join(extra)}")
        raise SemanticAnalysisError(f"{prefix} has " + "; ".join(details))

    indexes = value["source_indexes"]
    if not isinstance(indexes, list):
        raise SemanticAnalysisError(f"{prefix} source_indexes must be an array")
    if any(isinstance(index, bool) or not isinstance(index, int) for index in indexes):
        raise SemanticAnalysisError(
            f"{prefix} source_indexes must contain only integers"
        )
    topic = value["topic"]
    summary = value["summary"]
    if not isinstance(topic, str) or not topic.strip():
        raise SemanticAnalysisError(f"{prefix} topic must not be empty")
    if not isinstance(summary, str) or not summary.strip():
        raise SemanticAnalysisError(f"{prefix} summary must not be empty")
    importance = value["importance"]
    if (
        isinstance(importance, bool)
        or not isinstance(importance, (int, float))
        or not isfinite(importance)
        or not 0 <= importance <= 1
    ):
        raise SemanticAnalysisError(
            f"{prefix} importance must be between 0 and 1"
        )
    try:
        chunk_type = SemanticChunkType(value["chunk_type"])
    except (TypeError, ValueError) as error:
        raise SemanticAnalysisError(
            f"{prefix} contains invalid chunk_type: {value['chunk_type']!r}"
        ) from error
    return SemanticChunkProposal(
        source_indexes=tuple(indexes),
        topic=topic,
        summary=summary,
        chunk_type=chunk_type,
        importance=float(importance),
    )


def validate_semantic_analysis_result(
    result: SemanticAnalysisResult,
    source_count: int,
) -> None:
    """校验索引连续性、唯一性、顺序和完整覆盖。"""

    if (
        isinstance(source_count, bool)
        or not isinstance(source_count, int)
        or source_count < 0
    ):
        raise ValueError("source_count 必须是非负整数")
    seen: set[int] = set()
    previous_last = -1
    for proposal_position, proposal in enumerate(result.semantic_chunks):
        prefix = f"Semantic analysis proposal {proposal_position}"
        if not isinstance(proposal.topic, str) or not proposal.topic.strip():
            raise SemanticAnalysisError(f"{prefix} topic must not be empty")
        if not isinstance(proposal.summary, str) or not proposal.summary.strip():
            raise SemanticAnalysisError(f"{prefix} summary must not be empty")
        if not isinstance(proposal.chunk_type, SemanticChunkType):
            raise SemanticAnalysisError(
                f"{prefix} contains invalid chunk_type: "
                f"{proposal.chunk_type!r}"
            )
        if (
            isinstance(proposal.importance, bool)
            or not isinstance(proposal.importance, (int, float))
            or not isfinite(proposal.importance)
            or not 0 <= proposal.importance <= 1
        ):
            raise SemanticAnalysisError(
                f"{prefix} importance must be between 0 and 1"
            )
        indexes = proposal.source_indexes
        if not indexes:
            raise SemanticAnalysisError(
                f"{prefix} contains empty source_indexes"
            )
        proposal_seen: set[int] = set()
        for index in indexes:
            if isinstance(index, bool) or not isinstance(index, int):
                raise SemanticAnalysisError(
                    "Semantic analysis result contains non-integer "
                    f"source index: {index!r}"
                )
            if index < 0 or index >= source_count:
                raise SemanticAnalysisError(
                    "Semantic analysis result contains out-of-range "
                    f"source index: {index}"
                )
            if index in seen or index in proposal_seen:
                raise SemanticAnalysisError(
                    "Semantic analysis result contains duplicated "
                    f"source index: {index}"
                )
            proposal_seen.add(index)
        if any(right <= left for left, right in zip(indexes, indexes[1:])):
            raise SemanticAnalysisError(
                f"Semantic analysis proposal {proposal_position} "
                "source_indexes must be strictly increasing"
            )
        if any(right != left + 1 for left, right in zip(indexes, indexes[1:])):
            raise SemanticAnalysisError(
                f"Semantic analysis proposal {proposal_position} "
                "source_indexes must be continuous"
            )
        if indexes[0] <= previous_last:
            raise SemanticAnalysisError(
                "Semantic analysis proposals are not in source order"
            )
        seen.update(indexes)
        previous_last = indexes[-1]

    expected = set(range(source_count))
    missing = sorted(expected.difference(seen))
    if missing:
        raise SemanticAnalysisError(
            "Semantic analysis result is missing source indexes: "
            + ", ".join(str(index) for index in missing)
        )
