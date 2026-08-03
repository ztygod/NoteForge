from pathlib import Path

import pytest

from noteforge.document import DocumentSection, LearningDocument
from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.extraction import KnowledgePoint, KnowledgePointType
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic import SemanticChunk, SemanticChunkType
from noteforge.renderer import MarkdownRenderer, write_markdown


def make_point(
    title: str,
    *,
    start: float,
    end: float,
    point_type: KnowledgePointType = KnowledgePointType.CONCEPT,
    keywords: tuple[str, ...] = ("关键词",),
    explanation: str = "解释内容",
) -> KnowledgePoint:
    raw = RawChunk(start, end, explanation)
    preprocessed = PreprocessedChunk(start, end, explanation, (raw,))
    semantic = SemanticChunk(
        start_time=start,
        end_time=end,
        text=explanation,
        topic="主题",
        summary="摘要",
        chunk_type=SemanticChunkType.EXPLANATION,
        importance=0.8,
        source_chunks=(preprocessed,),
    )
    return KnowledgePoint(
        title=title,
        explanation=explanation,
        point_type=point_type,
        keywords=keywords,
        importance=0.8,
        source_chunks=(semantic,),
    )


def make_document() -> LearningDocument:
    first = make_point("概念一", start=0, end=10)
    second = make_point("流程一", start=10, end=20.5)
    third = make_point("流程二", start=20.5, end=30)
    return LearningDocument(
        title="测试笔记",
        summary="文档摘要",
        sections=(
            DocumentSection("基础概念", "概念描述", (first,)),
            DocumentSection("工作流程", "流程描述", (second, third)),
        ),
    )


def test_learning_document_renders_expected_structure() -> None:
    markdown = MarkdownRenderer().render(make_document())

    assert markdown.startswith("# 测试笔记\n\n> 文档摘要\n")
    assert "### 概念一\n\n解释内容" in markdown
    assert "\n类型:\n\nconcept\n" in markdown
    assert "\n关键词:\n\n- 关键词\n" in markdown
    assert markdown.endswith("---\n")


def test_section_and_knowledge_point_order_are_preserved() -> None:
    markdown = MarkdownRenderer().render(make_document())

    assert markdown.index("## 基础概念") < markdown.index("## 工作流程")
    assert markdown.index("### 流程一") < markdown.index("### 流程二")


def test_time_uses_compact_start_and_end_format() -> None:
    markdown = MarkdownRenderer().render(make_document())

    assert "0 - 10" in markdown
    assert "10 - 20.5" in markdown
    assert "20.5 - 30" in markdown


def test_structural_markdown_characters_are_escaped() -> None:
    point = make_point(
        "数组 [基础]",
        start=0,
        end=1,
        keywords=("a*b",),
        explanation="这里保留 **正文 Markdown**。",
    )
    document = LearningDocument(
        "C# 学习",
        "摘要 > 注意",
        (DocumentSection("概念 #1", "描述", (point,)),),
    )

    markdown = MarkdownRenderer().render(document)

    assert "# C\\# 学习" in markdown
    assert "> 摘要 \\> 注意" in markdown
    assert "## 概念 \\#1" in markdown
    assert "### 数组 \\[基础\\]" in markdown
    assert "- a\\*b" in markdown
    assert "这里保留 **正文 Markdown**。" in markdown


def test_empty_keywords_render_explicit_placeholder() -> None:
    point = make_point("无关键词", start=0, end=1, keywords=())
    document = LearningDocument(
        "笔记",
        "摘要",
        (DocumentSection("章节", "描述", (point,)),),
    )

    assert "关键词:\n\n（无）" in MarkdownRenderer().render(document)


def test_renderer_rejects_wrong_input_type() -> None:
    with pytest.raises(TypeError, match="LearningDocument"):
        MarkdownRenderer().render("错误")  # type: ignore[arg-type]


def test_write_markdown_creates_directories_and_uses_utf8(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nested" / "note.md"
    content = "# 中文笔记\n"

    result = write_markdown(content, output_path)

    assert result == output_path
    assert output_path.read_text(encoding="utf-8") == content
