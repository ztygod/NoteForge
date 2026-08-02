"""将视频来源转换为 Markdown 学习笔记，并发送各阶段事件。"""

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.core.events import EventHandler, PipelineEvent, PipelineStatus, null_event_handler
from noteforge.document import generate_document
from noteforge.exceptions import (
    NoteForgeError,
    PipelineErrorContext,
    PipelineExecutionError,
    UnsupportedSourceError,
)
from noteforge.knowledge.chunker import TranscriptChunker
from noteforge.knowledge.extraction import KnowledgeExtractor, KnowledgePointType, LLMKnowledgeExtractor
from noteforge.knowledge.preprocessor import ChunkPreprocessor
from noteforge.knowledge.semantic import LLMSemanticAnalyzer, SemanticAnalyzer
from noteforge.llm import LLMClient
from noteforge.llm.models import LLMMessage, LLMRequestOptions, LLMResponse
from noteforge.renderer import MarkdownRenderer, write_markdown


VideoCollector = Callable[..., VideoCollectionResult]


class _MeasuredLLMClient(LLMClient):
    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.call_count = 0
        self.retry_count = 0

    def generate(
        self,
        messages: list[LLMMessage] | tuple[LLMMessage, ...],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        return self.client.generate(messages, options=options)


def _json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


class NoteGenerationPipeline:
    """组合采集、知识提取、文档构建与 Markdown 渲染流程。"""

    def __init__(
        self,
        semantic_analyzer: SemanticAnalyzer,
        knowledge_extractor: KnowledgeExtractor,
        *,
        collector: VideoCollector = bilibili.collect_bilibili_video,
        event_handler: EventHandler | None = None,
        measured_client: _MeasuredLLMClient | None = None,
    ) -> None:
        self._semantic_analyzer = semantic_analyzer
        self._knowledge_extractor = knowledge_extractor
        self._collector = collector
        self._emit = event_handler or null_event_handler
        self._measured_client = measured_client

    def set_event_handler(self, handler: EventHandler) -> None:
        """在 Pipeline 运行前绑定或替换事件消费者。"""

        self._emit = handler

    @classmethod
    def from_llm_client(
        cls, client: LLMClient, *, event_handler: EventHandler | None = None
    ) -> "NoteGenerationPipeline":
        measured = _MeasuredLLMClient(client)
        return cls(
            LLMSemanticAnalyzer(measured),
            LLMKnowledgeExtractor(measured),
            event_handler=event_handler,
            measured_client=measured,
        )

    def _event(
        self, stage: str, status: PipelineStatus, message: str, **kwargs: Any
    ) -> None:
        self._emit(PipelineEvent(stage, status, message, **kwargs))

    async def run(
        self,
        source: str,
        output_path: str | Path,
        *,
        cookies_from_browser: str | None = "chrome",
        subtitle_language: str | None = None,
        subtitle_output_dir: Path = Path(".cache/noteforge/subtitles"),
        debug_dir: Path | None = None,
    ) -> Path:
        snapshots: dict[str, Any] = {}
        current_stage = "input"
        current_source_text: str | None = None
        started = perf_counter()

        async def async_stage(stage: str, message: str, operation: Any) -> Any:
            nonlocal current_stage
            current_stage = stage
            began = perf_counter()
            self._event(stage, PipelineStatus.RUNNING, message)
            result = await operation()
            self._event(stage, PipelineStatus.SUCCESS, message, duration=perf_counter() - began)
            return result

        def sync_stage(stage: str, message: str, operation: Any) -> Any:
            nonlocal current_stage
            current_stage = stage
            began = perf_counter()
            self._event(stage, PipelineStatus.RUNNING, message)
            result = operation()
            self._event(stage, PipelineStatus.SUCCESS, message, duration=perf_counter() - began)
            return result

        try:
            inspected = sync_stage("input", "Input validated", lambda: inspection.inspect_source(source))
            if inspected.platform is not inspection.InspectionPlatform.BILIBILI or inspected.normalized_source is None:
                raise UnsupportedSourceError(f"暂不支持该视频来源：{source}")

            collection = sync_stage(
                "transcript", "Transcript extracted",
                lambda: self._collector(
                    source=inspected.normalized_source,
                    cookies_from_browser=cookies_from_browser,
                    subtitle_language=subtitle_language,
                    subtitle_output_dir=subtitle_output_dir,
                    page_number=inspected.page_number,
                ),
            )
            if collection.transcript is None:
                raise NoteForgeError("视频没有可供处理的受支持字幕")
            self._event(
                "transcript",
                PipelineStatus.SUCCESS,
                "Transcript metrics",
                metrics={
                    "segments": len(collection.transcript.segments),
                    "video_duration_minutes": (
                        round(collection.metadata.duration / 60, 2)
                        if collection.metadata.duration is not None
                        else None
                    ),
                },
            )

            raw_chunks = sync_stage("chunk", "Raw chunks created", lambda: TranscriptChunker().chunk(collection.transcript))
            snapshots["raw_chunks.json"] = raw_chunks
            self._event("chunk", PipelineStatus.SUCCESS, "Raw chunks counted", metrics={"raw_chunks": len(raw_chunks)})

            preprocessed_chunks = sync_stage("preprocess", "Chunks preprocessed", lambda: ChunkPreprocessor().preprocess(raw_chunks))
            self._event("preprocess", PipelineStatus.SUCCESS, "Preprocessed chunks counted", metrics={"preprocessed_chunks": len(preprocessed_chunks)})

            semantic_chunks = await async_stage("semantic", "Semantic chunks generated", lambda: self._semantic_analyzer.analyze(preprocessed_chunks))
            snapshots["semantic_chunks.json"] = semantic_chunks
            current_source_text = "\n".join(chunk.text for chunk in semantic_chunks)
            self._event("semantic", PipelineStatus.SUCCESS, "Semantic chunks counted", metrics={"semantic_chunks": len(semantic_chunks)})

            knowledge_points = await async_stage("knowledge", "Knowledge generated", lambda: self._knowledge_extractor.extract(semantic_chunks))
            if not knowledge_points:
                raise NoteForgeError("未能从视频字幕中提取出知识点")
            snapshots["knowledge_points.json"] = knowledge_points
            counts: dict[str, int] = {}
            for point in knowledge_points:
                counts[point.point_type.value] = counts.get(point.point_type.value, 0) + 1
            metrics: dict[str, Any] = {"knowledge_points": len(knowledge_points), "types": counts}
            if self._measured_client:
                metrics.update(llm_calls=self._measured_client.call_count, retries=self._measured_client.retry_count)
            self._event("knowledge", PipelineStatus.SUCCESS, "Knowledge points counted", metrics=metrics)

            document = sync_stage("document", "Document built", lambda: generate_document(knowledge_points))
            snapshots["document.json"] = document
            markdown = sync_stage("markdown", "Markdown rendered", lambda: MarkdownRenderer().render(document))
            result = sync_stage("output", "Markdown saved", lambda: write_markdown(markdown, output_path))
            self._event("pipeline", PipelineStatus.SUCCESS, "Finished", duration=perf_counter() - started)
            return result
        except Exception as error:
            self._event(current_stage, PipelineStatus.ERROR, str(error), duration=perf_counter() - started)
            if debug_dir is not None:
                debug_dir.mkdir(parents=True, exist_ok=True)
                for filename in ("raw_chunks.json", "semantic_chunks.json", "knowledge_points.json", "document.json"):
                    (debug_dir / filename).write_text(
                        json.dumps(_json_value(snapshots.get(filename)), ensure_ascii=False, indent=2), encoding="utf-8"
                    )
            if isinstance(error, PipelineExecutionError):
                raise
            match = re.search(r"Knowledge point (\d+).*invalid point_type:\s*(.+)", str(error), re.IGNORECASE)
            context = PipelineErrorContext(
                stage={"knowledge": "KnowledgePointBuilder"}.get(current_stage, current_stage),
                object_name=f"KnowledgePoint #{match.group(1)}" if match else None,
                reason=f"Invalid point_type:\n{match.group(2).strip()}" if match else str(error),
                allowed_values=tuple(item.value for item in KnowledgePointType) if match else (),
                source_text=current_source_text,
            )
            raise PipelineExecutionError(context, error) from error
