import asyncio
from pathlib import Path

from noteforge.media.models import Subtitle, SubtitleSegment, VideoMetadata, VideoResource
from noteforge.core import NoteGenerationPipeline
from noteforge.core.events import PipelineEvent
from noteforge.knowledge.extraction import KnowledgePoint, KnowledgePointType
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic import SemanticChunk, SemanticChunkType


class StaticSemanticAnalyzer:
    """测试用语义分析器，保留 Pipeline 传入的真实预处理块。"""

    async def analyze(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        return (
            SemanticChunk(
                start_time=chunks[0].start_time,
                end_time=chunks[-1].end_time,
                text="\n".join(chunk.text for chunk in chunks),
                topic="TCP",
                summary="TCP 基础",
                chunk_type=SemanticChunkType.EXPLANATION,
                importance=0.8,
                source_chunks=chunks,
            ),
        )


class StaticKnowledgeExtractor:
    """测试用知识提取器，保留 Pipeline 传入的真实语义块。"""

    async def extract(
        self,
        chunks: tuple[SemanticChunk, ...],
    ) -> tuple[KnowledgePoint, ...]:
        return (
            KnowledgePoint(
                title="TCP 是什么",
                explanation="TCP 是可靠的传输层协议。",
                point_type=KnowledgePointType.CONCEPT,
                keywords=("TCP",),
                importance=0.8,
                source_chunks=chunks,
            ),
        )


class MemoryArtifactSink:
    def __init__(self) -> None:
        self.artifacts = {}

    def save_artifact(self, name, value):
        self.artifacts[name] = value
        return Path(name)

    def save_note(self, markdown):
        self.artifacts["note"] = markdown
        return Path("note.md")


def make_collection(source: str) -> VideoResource:
    """创建带结构化字幕的采集结果。"""

    return VideoResource(
        metadata=VideoMetadata(
            id="BV1CkArz1E4o",
            title="TCP 教程",
            uploader=None,
            duration=10,
            thumbnail=None,
            platform="bilibili",
            webpage_url=source,
            description=None,
        ),
        subtitles=(Subtitle("zh-CN", "vtt"),),
        transcript=(
            SubtitleSegment(0, 5, "TCP 是传输层协议"),
            SubtitleSegment(5, 10, "TCP 提供可靠传输"),
        ),
        transcript_source="manual_subtitle",
    )


def test_pipeline_runs_video_to_markdown_flow(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "note.md"
    received: list[str] = []
    sink = MemoryArtifactSink()

    def collect(*, source: str, **_: object) -> VideoResource:
        received.append(source)
        return make_collection(source)

    pipeline = NoteGenerationPipeline(
        StaticSemanticAnalyzer(),
        StaticKnowledgeExtractor(),
        collector=collect,
        artifact_sink=sink,
    )
    result = asyncio.run(
        pipeline.run(
            "https://www.bilibili.com/video/BV1CkArz1E4o",
            output_path,
        )
    )

    assert received == [
        "https://www.bilibili.com/video/BV1CkArz1E4o"
    ]
    assert result == output_path
    content = result.read_text(encoding="utf-8")
    assert content.startswith("# TCP学习笔记")
    assert "## 基础概念" in content
    assert "### TCP 是什么" in content
    assert "0 - 10" in content
    assert set(sink.artifacts) == {
        "transcript",
        "raw_chunks",
        "preprocessed_chunks",
        "semantic_chunks",
        "knowledge_points",
        "document",
        "note",
    }


def test_activity_event_keeps_completed_progress_separate_from_active_batch() -> None:
    events: list[PipelineEvent] = []
    pipeline = NoteGenerationPipeline(
        StaticSemanticAnalyzer(),
        StaticKnowledgeExtractor(),
        event_handler=events.append,
    )

    pipeline._batch_event(
        "semantic",
        "Semantic chunks generated",
        current=2,
        total=6,
        completed=True,
    )
    pipeline._llm_activity(
        "semantic",
        "requesting_model",
        {"batch_current": 5, "batch_total": 6, "attempt": 1},
    )

    event = events[-1]
    assert event.progress == 2 / 6
    assert event.metrics["batch_completed"] == 2
    assert event.metrics["active_batch"] == 5
    assert event.metrics["batch_total"] == 6
