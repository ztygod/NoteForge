import json

import pytest

from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.models import Concept, Evidence, KnowledgeChunk
from noteforge.knowledge.prompts import (
    BasePrompt,
    ChunkAnalysisPrompt,
    ConceptExtractionPrompt,
)


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
