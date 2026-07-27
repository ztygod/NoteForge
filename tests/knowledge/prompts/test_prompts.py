import json

import pytest

from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.models import Concept, Evidence, KnowledgeChunk
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.prompts import (
    BasePrompt,
    ChunkAnalysisPrompt,
    ConceptExtractionPrompt,
    KnowledgeExtractionPrompt,
    SemanticAnalysisPrompt,
)
from noteforge.knowledge.semantic import SemanticChunk, SemanticChunkType


class ExamplePrompt(BasePrompt):
    system_template = "任务：{task}"
    user_template = "输入：{content}"


def test_base_prompt_injects_variables() -> None:
    messages = ExamplePrompt().build_messages(
        {"task": "分析", "content": "字幕"}
    )

    assert messages[0].role == "system"
    assert messages[0].content == "任务：分析"
    assert messages[1].role == "user"
    assert messages[1].content == "输入：字幕"


def test_base_prompt_reports_missing_variable() -> None:
    with pytest.raises(ValueError, match="content"):
        ExamplePrompt().build_user_prompt({})


def test_chunk_analysis_prompt_preserves_transcript_and_timestamps() -> None:
    chunk = RawChunk(1.2, 3.4567, "模型只能依据这段字幕。")

    system_message, user_message = ChunkAnalysisPrompt().build_for_chunk(chunk)

    assert '"topic"' in system_message.content
    assert '"summary"' in system_message.content
    assert '"concepts"' in system_message.content
    assert '"evidence"' in system_message.content
    assert "只输出一个合法 JSON 对象" in system_message.content
    assert "1.200 至 3.457" in user_message.content
    assert "模型只能依据这段字幕。" in user_message.content


def test_concept_extraction_prompt_serializes_existing_evidence() -> None:
    chunk = KnowledgeChunk(
        id="chunk-1",
        video_id="video-1",
        video_title="课程",
        start_time=10,
        end_time=20,
        topic="测试",
        summary="基于证据的总结",
        concepts=[
            Concept(
                name="证据",
                description="用于支持结论",
                evidence=[Evidence(timestamp=12.5, text="原始字幕")],
            )
        ],
    )

    system_message, user_message = (
        ConceptExtractionPrompt().build_for_chunk(chunk)
    )

    assert '"relationships"' in system_message.content
    serialized = user_message.content.split(
        "<knowledge_chunk>\n", 1
    )[1].split("\n</knowledge_chunk>", 1)[0]
    payload = json.loads(serialized)
    assert payload["concepts"][0]["evidence"][0] == {
        "text": "原始字幕",
        "timestamp": 12.5,
    }


def test_semantic_analysis_prompt_assigns_stable_indexes() -> None:
    raw_chunks = (
        RawChunk(0.66, 5.2, "闭包能够访问外层变量。"),
        RawChunk(5.2, 10.14, "这里给出一个闭包示例。"),
    )
    chunks = tuple(
        PreprocessedChunk(
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            text=chunk.text,
            source_chunks=(chunk,),
        )
        for chunk in raw_chunks
    )

    system_message, user_message = (
        SemanticAnalysisPrompt().build_for_chunks(chunks)
    )

    assert '"source_indexes"' in system_message.content
    assert "不返回时间、原始文本或来源对象" in system_message.content
    assert "[0]\n时间：0.660 - 5.200" in user_message.content
    assert "[1]\n时间：5.200 - 10.140" in user_message.content
    assert "闭包能够访问外层变量。" in user_message.content


def test_knowledge_extraction_prompt_contains_semantic_context() -> None:
    raw = RawChunk(12.4, 26.8, "闭包能够访问定义作用域中的变量。")
    preprocessed = PreprocessedChunk(12.4, 26.8, raw.text, (raw,))
    chunk = SemanticChunk(
        start_time=12.4,
        end_time=26.8,
        text=raw.text,
        topic="闭包的定义",
        summary="解释闭包如何保留词法作用域中的变量",
        chunk_type=SemanticChunkType.DEFINITION,
        importance=0.91,
        source_chunks=(preprocessed,),
    )

    system_message, user_message = (
        KnowledgeExtractionPrompt().build_for_chunks(
            (chunk,),
            start_index=3,
        )
    )

    assert '"knowledge_points"' in system_message.content
    assert "不要求覆盖全部输入索引" in system_message.content
    assert "[3]\n时间：12.400 - 26.800" in user_message.content
    assert "主题：闭包的定义" in user_message.content
    assert "类型：definition" in user_message.content
    assert "重要程度：0.910" in user_message.content
    assert f"正文：\n{raw.text}" in user_message.content
