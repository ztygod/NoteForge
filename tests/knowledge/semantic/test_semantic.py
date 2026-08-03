import asyncio
import json
from typing import Sequence

import pytest

from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic import (
    LLMSemanticAnalyzer,
    SemanticAnalysisError,
    SemanticAnalysisResult,
    SemanticChunkProposal,
    SemanticChunkType,
    validate_semantic_analysis_result,
)
from noteforge.llm import (
    LLMClient,
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
)


class StaticClient(LLMClient):
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[Sequence[LLMMessage]] = []

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        self.messages.append(messages)
        return LLMResponse(content=self.content, model="test")


class SequenceClient(StaticClient):
    def __init__(self, contents: list[str]) -> None:
        super().__init__("")
        self.contents = iter(contents)

    async def generate(self, messages, *, options=None):
        self.messages.append(messages)
        return LLMResponse(content=next(self.contents), model="test")


class ConcurrentClient(StaticClient):
    def __init__(self, content: str) -> None:
        super().__init__(content)
        self.active = 0
        self.max_active = 0

    async def generate(self, messages, *, options=None):
        self.messages.append(messages)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return LLMResponse(content=self.content, model="test")


def make_chunk(start: float, end: float, text: str) -> PreprocessedChunk:
    raw = RawChunk(start, end, text)
    return PreprocessedChunk(start, end, text, (raw,))


def proposal(
    indexes: list[int],
    *,
    topic: str = "主题",
    chunk_type: str = "explanation",
    importance: float = 0.8,
) -> dict[str, object]:
    return {
        "source_indexes": indexes,
        "topic": topic,
        "summary": f"{topic}摘要",
        "chunk_type": chunk_type,
        "importance": importance,
    }


def response(*proposals: dict[str, object]) -> str:
    return json.dumps({"semantic_chunks": proposals}, ensure_ascii=False)


def analyze(
    content: str,
    chunks: tuple[PreprocessedChunk, ...],
    *,
    batch_size: int = 20,
):
    client = StaticClient(content)
    result = asyncio.run(
        LLMSemanticAnalyzer(client, batch_size=batch_size).analyze(chunks)
    )
    return result, client


def test_reports_progress_before_and_after_each_batch(monkeypatch) -> None:
    events: list[tuple[int, int, bool]] = []
    analyzer = LLMSemanticAnalyzer(
        StaticClient("{}"),
        batch_size=2,
        progress_handler=lambda current, total, completed: events.append(
            (current, total, completed)
        ),
    )

    async def fake_analyze_batch(chunks, **options):
        return ()

    monkeypatch.setattr(analyzer, "_analyze_batch", fake_analyze_batch)
    chunks = tuple(make_chunk(index, index + 1, str(index)) for index in range(3))

    asyncio.run(analyzer.analyze(chunks))

    assert events == [(1, 2, False), (1, 2, True), (2, 2, True)]


def test_batches_run_with_bounded_concurrency_and_keep_order() -> None:
    chunks = tuple(make_chunk(index, index + 1, str(index)) for index in range(4))
    client = ConcurrentClient(response(proposal([0])))
    analyzer = LLMSemanticAnalyzer(
        client, batch_size=1, max_concurrency=2
    )

    result = asyncio.run(analyzer.analyze(chunks))

    assert client.max_active == 2
    assert [chunk.text for chunk in result] == ["0", "1", "2", "3"]


def test_single_input_produces_one_semantic_chunk() -> None:
    chunk = make_chunk(0.5, 2, "闭包可以访问外层变量")

    result, client = analyze(response(proposal([0])), (chunk,))

    assert len(result) == 1
    assert result[0].source_chunks == (chunk,)
    assert "[0]" in client.messages[0][1].content


def test_validation_failure_is_retried_once_with_feedback() -> None:
    chunks = (make_chunk(0, 1, "一"), make_chunk(1, 2, "二"))
    client = SequenceClient([
        response(proposal([0])),
        response(proposal([0, 1])),
    ])
    activities: list[tuple[str, dict[str, object]]] = []
    analyzer = LLMSemanticAnalyzer(
        client, activity_handler=lambda operation, data: activities.append((operation, data))
    )

    result = asyncio.run(analyzer.analyze(chunks))

    assert len(result) == 1
    assert len(client.messages) == 2
    assert "missing source indexes" in client.messages[1][-1].content
    assert "retrying_validation" in [operation for operation, _ in activities]


def test_merges_inputs_and_rebuilds_time_and_text() -> None:
    chunks = (
        make_chunk(0.5, 2, "第一段"),
        make_chunk(2, 4.5, "第二段"),
    )

    result, _ = analyze(response(proposal([0, 1])), chunks)

    assert result[0].start_time == 0.5
    assert result[0].end_time == 4.5
    assert result[0].text == "第一段\n第二段"
    assert result[0].source_chunks == chunks


def test_multiple_topics_produce_multiple_chunks() -> None:
    chunks = (
        make_chunk(0, 1, "定义"),
        make_chunk(1, 2, "解释"),
        make_chunk(2, 3, "例子"),
    )
    content = response(
        proposal([0, 1], topic="概念"),
        proposal([2], topic="例子", chunk_type="example"),
    )

    result, _ = analyze(content, chunks)

    assert [item.topic for item in result] == ["概念", "例子"]
    assert result[1].chunk_type is SemanticChunkType.EXAMPLE


def test_comparison_is_a_supported_semantic_chunk_type() -> None:
    chunk = make_chunk(0, 1, "两种方案的优缺点对比")

    result, _ = analyze(
        response(proposal([0], chunk_type="comparison")),
        (chunk,),
    )

    assert result[0].chunk_type is SemanticChunkType.COMPARISON


def validation_result(
    *indexes: tuple[int, ...],
) -> SemanticAnalysisResult:
    return SemanticAnalysisResult(
        tuple(
            SemanticChunkProposal(
                source_indexes=value,
                topic="主题",
                summary="摘要",
                chunk_type=SemanticChunkType.OTHER,
                importance=0.5,
            )
            for value in indexes
        )
    )


@pytest.mark.parametrize(
    ("result", "source_count", "message"),
    [
        (validation_result((0, 2)), 3, "continuous"),
        (validation_result((0, 0), (1,)), 2, "duplicated"),
        (validation_result((0,), (0, 1)), 2, "duplicated"),
        (validation_result((0,), (2,)), 2, "out-of-range"),
        (validation_result((0,), (2,)), 3, "missing"),
        (validation_result((1,), (0,)), 2, "source order"),
        (validation_result(()), 1, "empty source_indexes"),
    ],
)
def test_rejects_invalid_index_mapping(
    result: SemanticAnalysisResult,
    source_count: int,
    message: str,
) -> None:
    with pytest.raises(SemanticAnalysisError, match=message):
        validate_semantic_analysis_result(result, source_count)


@pytest.mark.parametrize(
    ("changed_field", "value", "message"),
    [
        ("importance", 1.1, "importance"),
        ("chunk_type", "invalid", "chunk_type"),
        ("topic", "", "topic"),
    ],
)
def test_rejects_invalid_proposal_fields(
    changed_field: str,
    value: object,
    message: str,
) -> None:
    item = proposal([0])
    item[changed_field] = value

    with pytest.raises(SemanticAnalysisError, match=message):
        analyze(response(item), (make_chunk(0, 1, "文本"),))


def test_empty_input_does_not_call_llm() -> None:
    result, client = analyze("not json", ())

    assert result == ()
    assert client.messages == []


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"semantic_chunks": "wrong"}',
        '{"semantic_chunks": [{"source_indexes": [0]}]}',
        '{"semantic_chunks": [], "start_time": 0}',
    ],
)
def test_invalid_json_or_structure_raises_clear_error(content: str) -> None:
    with pytest.raises(SemanticAnalysisError):
        analyze(content, (make_chunk(0, 1, "文本"),))


def test_fixed_size_batching_uses_local_stable_indexes() -> None:
    chunks = (
        make_chunk(0, 1, "一"),
        make_chunk(1, 2, "二"),
    )
    result, client = analyze(response(proposal([0])), chunks, batch_size=1)

    assert len(result) == 2
    assert len(client.messages) == 2
    assert "[1]" not in client.messages[1][1].content
