from dataclasses import FrozenInstanceError

import pytest

from noteforge.document import (
    DocumentSection,
    KnowledgeDocumentBuilder,
    LearningDocument,
    generate_document,
)
from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.extraction import KnowledgePoint, KnowledgePointType
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic import SemanticChunk, SemanticChunkType


def make_point(
    title: str,
    point_type: KnowledgePointType = KnowledgePointType.CONCEPT,
    *,
    keywords: tuple[str, ...] = ("TCP",),
    index: int = 0,
) -> KnowledgePoint:
    start = float(index)
    end = start + 1
    raw = RawChunk(start, end, title)
    preprocessed = PreprocessedChunk(start, end, title, (raw,))
    semantic = SemanticChunk(
        start_time=start,
        end_time=end,
        text=title,
        topic="TCP",
        summary=title,
        chunk_type=SemanticChunkType.EXPLANATION,
        importance=0.8,
        source_chunks=(preprocessed,),
    )
    return KnowledgePoint(
        title=title,
        explanation=f"{title}的解释",
        point_type=point_type,
        keywords=keywords,
        importance=0.8,
        source_chunks=(semantic,),
    )


def test_models_are_frozen_and_use_slots() -> None:
    point = make_point("TCP是什么")
    section = DocumentSection("基础概念", "基础定义。", (point,))
    document = LearningDocument("TCP学习笔记", "学习摘要。", (section,))

    assert not hasattr(section, "__dict__")
    assert not hasattr(document, "__dict__")
    with pytest.raises(FrozenInstanceError):
        section.title = "新标题"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        document.title = "新标题"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", " 标题"),
        ("description", " "),
        ("description", "描述 "),
    ],
)
def test_section_rejects_invalid_text(field: str, value: str) -> None:
    values = {
        "title": "标题",
        "description": "描述",
        "knowledge_points": (make_point("知识点"),),
    }
    values[field] = value

    with pytest.raises(ValueError):
        DocumentSection(**values)  # type: ignore[arg-type]


def test_section_validates_knowledge_points_and_duplicate_references() -> None:
    point = make_point("知识点")

    with pytest.raises(TypeError, match="tuple"):
        DocumentSection("标题", "描述", [point])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="至少一个"):
        DocumentSection("标题", "描述", ())
    with pytest.raises(TypeError, match="KnowledgePoint"):
        DocumentSection("标题", "描述", ("错误",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="重复引用"):
        DocumentSection("标题", "描述", (point, point))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", " 标题"),
        ("summary", " "),
        ("summary", "摘要 "),
    ],
)
def test_document_rejects_invalid_text(field: str, value: str) -> None:
    section = DocumentSection(
        "基础概念",
        "基础定义。",
        (make_point("知识点"),),
    )
    values = {
        "title": "学习笔记",
        "summary": "摘要",
        "sections": (section,),
    }
    values[field] = value

    with pytest.raises(ValueError):
        LearningDocument(**values)  # type: ignore[arg-type]


def test_document_validates_sections() -> None:
    point = make_point("知识点")
    section = DocumentSection("标题", "描述", (point,))

    with pytest.raises(TypeError, match="tuple"):
        LearningDocument("标题", "摘要", [section])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="至少一个"):
        LearningDocument("标题", "摘要", ())
    with pytest.raises(TypeError, match="DocumentSection"):
        LearningDocument("标题", "摘要", ("错误",))  # type: ignore[arg-type]


def test_builder_groups_types_in_fixed_order_and_preserves_input_order() -> None:
    points = (
        make_point("例子", KnowledgePointType.EXAMPLE, index=0),
        make_point("流程一", KnowledgePointType.PROCEDURE, index=1),
        make_point("概念", KnowledgePointType.CONCEPT, index=2),
        make_point("流程二", KnowledgePointType.PROCEDURE, index=3),
        make_point("原理", KnowledgePointType.PRINCIPLE, index=4),
        make_point("对比", KnowledgePointType.COMPARISON, index=5),
        make_point("注意", KnowledgePointType.PITFALL, index=6),
    )

    document = KnowledgeDocumentBuilder().build(points)

    assert [section.title for section in document.sections] == [
        "基础概念",
        "核心原理",
        "工作流程",
        "示例解析",
        "对比分析",
        "其他知识",
    ]
    assert [
        point.title for point in document.sections[2].knowledge_points
    ] == ["流程一", "流程二"]
    assert document.sections[-1].knowledge_points == (points[-1],)


def test_builder_keeps_original_knowledge_point_references() -> None:
    point = make_point("TCP是什么")

    document = KnowledgeDocumentBuilder().build((point,))

    assert document.sections[0].knowledge_points[0] is point


def test_builder_infers_title_and_summary_deterministically() -> None:
    points = (
        make_point("定义", keywords=("网络", "TCP"), index=0),
        make_point(
            "握手",
            KnowledgePointType.PROCEDURE,
            keywords=("TCP",),
            index=1,
        ),
    )

    document = generate_document(points)

    assert document.title == "TCP学习笔记"
    assert document.summary == (
        "本文档整理了 2 个知识点，涵盖基础概念、工作流程。"
    )


def test_title_falls_back_to_first_point_when_keywords_are_empty() -> None:
    point = make_point("闭包", keywords=())

    document = generate_document((point,))

    assert document.title == "闭包学习笔记"


def test_equal_frequency_keywords_use_first_seen_order() -> None:
    points = (
        make_point("第一", keywords=("网络",), index=0),
        make_point("第二", keywords=("TCP",), index=1),
    )

    assert generate_document(points).title == "网络学习笔记"


def test_builder_rejects_invalid_or_empty_input() -> None:
    builder = KnowledgeDocumentBuilder()

    with pytest.raises(TypeError, match="tuple"):
        builder.build([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="不能为空"):
        builder.build(())
    with pytest.raises(TypeError, match="KnowledgePoint"):
        builder.build(("错误",))  # type: ignore[arg-type]
