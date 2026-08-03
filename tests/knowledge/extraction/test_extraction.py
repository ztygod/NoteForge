import asyncio
import json
from typing import Sequence

import pytest

from noteforge.exceptions import (
    KnowledgeExtractionError,
    LLMRequestError,
)
from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.extraction import (
    KnowledgeExtractionResult,
    KnowledgePointProposal,
    KnowledgePointType,
    LLMKnowledgeExtractor,
    build_knowledge_point,
    validate_knowledge_proposals,
)
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic import SemanticChunk, SemanticChunkType
from noteforge.llm import (
    LLMClient,
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
)


class StaticClient(LLMClient):
    def __init__(
        self,
        content: str,
        *,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.messages: list[Sequence[LLMMessage]] = []

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        return LLMResponse(content=self.content, model="test")


def make_semantic(
    index: int,
    *,
    chunk_type: SemanticChunkType = SemanticChunkType.EXPLANATION,
) -> SemanticChunk:
    start = float(index * 10)
    end = start + 10
    raw = RawChunk(start, end, f"正文{index}")
    preprocessed = PreprocessedChunk(start, end, raw.text, (raw,))
    return SemanticChunk(
        start_time=start,
        end_time=end,
        text=raw.text,
        topic=f"主题{index}",
        summary=f"摘要{index}",
        chunk_type=chunk_type,
        importance=0.8,
        source_chunks=(preprocessed,),
    )


def proposal(
    indexes: list[int],
    *,
    title: str = "闭包",
    explanation: str = "闭包能够保存词法作用域中的状态。",
    point_type: str = "concept",
    keywords: list[str] | None = None,
    importance: float = 0.9,
) -> dict[str, object]:
    return {
        "source_indexes": indexes,
        "title": title,
        "explanation": explanation,
        "point_type": point_type,
        "keywords": keywords if keywords is not None else ["闭包", "作用域"],
        "importance": importance,
    }


def response(*points: dict[str, object]) -> str:
    return json.dumps({"knowledge_points": points}, ensure_ascii=False)


def extract(
    content: str,
    chunks: tuple[SemanticChunk, ...],
    *,
    batch_size: int = 20,
    error: Exception | None = None,
):
    client = StaticClient(content, error=error)
    result = asyncio.run(
        LLMKnowledgeExtractor(client, batch_size=batch_size).extract(chunks)
    )
    return result, client


def test_reports_progress_before_and_after_each_batch(monkeypatch) -> None:
    events: list[tuple[int, int, bool]] = []
    extractor = LLMKnowledgeExtractor(
        StaticClient("{}"),
        batch_size=2,
        progress_handler=lambda current, total, completed: events.append(
            (current, total, completed)
        ),
    )

    async def fake_extract_batch(chunks, **options):
        return ()

    monkeypatch.setattr(extractor, "_extract_batch", fake_extract_batch)
    chunks = tuple(make_semantic(index) for index in range(3))

    asyncio.run(extractor.extract(chunks))

    assert events == [(1, 2, False), (1, 2, True), (2, 2, True)]


def test_empty_input_returns_empty_without_llm_call() -> None:
    result, client = extract("not json", ())

    assert result == ()
    assert client.messages == []


def test_single_chunk_extracts_one_point() -> None:
    chunk = make_semantic(0)

    result, client = extract(response(proposal([0])), (chunk,))

    assert len(result) == 1
    assert result[0].source_chunks == (chunk,)
    assert "[0]" in client.messages[0][1].content


def test_multiple_continuous_chunks_build_one_point_with_source_time() -> None:
    chunks = (make_semantic(0), make_semantic(1))

    result, _ = extract(response(proposal([0, 1])), chunks)

    assert result[0].source_chunks == chunks
    assert result[0].start_time == chunks[0].start_time
    assert result[0].end_time == chunks[-1].end_time


def test_one_chunk_can_extract_multiple_points() -> None:
    chunk = make_semantic(0)
    content = response(
        proposal([0], title="定义"),
        proposal([0], title="应用", point_type="example"),
    )

    result, _ = extract(content, (chunk,))

    assert [point.title for point in result] == ["定义", "应用"]
    assert all(point.source_chunks == (chunk,) for point in result)


def test_points_can_reuse_sources_and_skip_other_inputs() -> None:
    chunks = tuple(make_semantic(index) for index in range(3))
    content = response(
        proposal([0, 1], title="定义"),
        proposal([1], title="注意事项", point_type="pitfall"),
    )

    result, _ = extract(content, chunks)

    assert result[0].source_chunks == chunks[:2]
    assert result[1].source_chunks == (chunks[1],)
    assert chunks[2] not in {
        source for point in result for source in point.source_chunks
    }


def proposal_model(
    indexes: tuple[object, ...] = (0,),
    *,
    title: object = "标题",
    explanation: object = "解释",
    point_type: object = KnowledgePointType.CONCEPT,
    keywords: tuple[object, ...] = ("关键词",),
    importance: object = 0.8,
) -> KnowledgePointProposal:
    return KnowledgePointProposal(
        source_indexes=indexes,  # type: ignore[arg-type]
        title=title,  # type: ignore[arg-type]
        explanation=explanation,  # type: ignore[arg-type]
        point_type=point_type,  # type: ignore[arg-type]
        keywords=keywords,  # type: ignore[arg-type]
        importance=importance,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("item", "source_count", "message"),
    [
        (proposal_model(()), 1, "empty source_indexes"),
        (proposal_model((1,)), 1, "out-of-range"),
        (proposal_model((-1,)), 1, "out-of-range"),
        (proposal_model((0, 0)), 1, "duplicated"),
        (proposal_model((1, 0)), 2, "non-increasing"),
        (proposal_model((0, 2)), 3, "non-contiguous"),
        (proposal_model((0.0,)), 1, "non-integer"),
        (proposal_model(title=" "), 1, "title"),
        (proposal_model(explanation=""), 1, "explanation"),
        (proposal_model(keywords=("",)), 1, "empty"),
        (proposal_model(keywords=("词", " 词 ")), 1, "duplicated keyword"),
        (proposal_model(keywords=()), 1, "between 1 and 6"),
        (proposal_model(importance=1.1), 1, "importance"),
        (proposal_model(importance=float("nan")), 1, "importance"),
        (proposal_model(importance=float("inf")), 1, "importance"),
        (proposal_model(point_type="invalid"), 1, "point_type"),
    ],
)
def test_validation_rejects_invalid_proposals(
    item: KnowledgePointProposal,
    source_count: int,
    message: str,
) -> None:
    with pytest.raises(KnowledgeExtractionError, match=message):
        validate_knowledge_proposals((item,), source_count)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"knowledge_points": "wrong"}',
        '{"knowledge_points": [{"source_indexes": [0]}]}',
        '{"knowledge_points": [], "start_time": 0}',
        response(proposal([0], point_type="invalid")),
    ],
)
def test_invalid_json_or_structure_raises_domain_error(content: str) -> None:
    with pytest.raises(KnowledgeExtractionError):
        extract(content, (make_semantic(0),))


def test_results_are_stably_sorted_by_first_source_index() -> None:
    chunks = tuple(make_semantic(index) for index in range(3))
    content = response(
        proposal([2], title="第三"),
        proposal([0], title="第一甲"),
        proposal([0, 1], title="第一乙"),
    )

    result, _ = extract(content, chunks)

    assert [point.title for point in result] == ["第一甲", "第一乙", "第三"]


def test_builder_normalizes_text_and_keywords() -> None:
    chunks = (make_semantic(0),)
    item = proposal_model(
        title="  标题  ",
        explanation="  完整解释  ",
        keywords=(" 甲 ", "", "乙", "甲"),
    )

    result = build_knowledge_point(chunks, item)

    assert result.title == "标题"
    assert result.explanation == "完整解释"
    assert result.keywords == ("甲", "乙")


def test_batch_prompt_uses_global_indexes_and_maps_original_objects() -> None:
    chunks = (make_semantic(0), make_semantic(1))
    client = StaticClient(response(proposal([1])))
    extractor = LLMKnowledgeExtractor(client, batch_size=1)

    result = asyncio.run(
        extractor._extract_batch(
            chunks[1:],
            start_index=1,
            all_chunks=chunks,
        )
    )

    assert result[0].source_chunks == (chunks[1],)
    assert "[1]" in client.messages[0][1].content
    assert "[0]" not in client.messages[0][1].content


def test_batch_cannot_reference_source_outside_current_batch() -> None:
    chunks = (make_semantic(0), make_semantic(1))

    with pytest.raises(KnowledgeExtractionError, match="current batch"):
        extract(response(proposal([1])), chunks, batch_size=1)


def test_client_error_is_wrapped_as_domain_error() -> None:
    with pytest.raises(
        KnowledgeExtractionError,
        match="model request failed",
    ):
        extract(
            response(),
            (make_semantic(0),),
            error=LLMRequestError("服务不可用"),
        )
