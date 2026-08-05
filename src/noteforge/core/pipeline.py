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
from noteforge.llm.models import (
    LLMMessage, LLMRequestOptions, LLMResponse, LLMTool, LLMToolResponse,
)
from noteforge.renderer import MarkdownRenderer, write_markdown


VideoCollector = Callable[..., VideoCollectionResult]


class _MeasuredLLMClient(LLMClient):
    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.call_count = 0
        self.retry_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_model: str | None = None

    async def generate(
        self,
        messages: list[LLMMessage] | tuple[LLMMessage, ...],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        response = await self.client.generate(messages, options=options)
        self.last_model = response.model
        self.input_tokens += response.usage.input_tokens or 0
        self.output_tokens += response.usage.output_tokens or 0
        return response

    async def call_tool(
        self,
        messages: list[LLMMessage] | tuple[LLMMessage, ...],
        *,
        tool: LLMTool,
        options: LLMRequestOptions | None = None,
    ) -> LLMToolResponse:
        self.call_count += 1
        response = await self.client.call_tool(messages, tool=tool, options=options)
        self.last_model = response.model
        self.input_tokens += response.usage.input_tokens or 0
        self.output_tokens += response.usage.output_tokens or 0
        return response

    async def aclose(self) -> None:
        await self.client.aclose()


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
        self._stage_progress: dict[str, float] = {}

    def set_event_handler(self, handler: EventHandler) -> None:
        """在 Pipeline 运行前绑定或替换事件消费者。"""

        self._emit = handler

    @classmethod
    def from_llm_client(
        cls,
        client: LLMClient,
        *,
        event_handler: EventHandler | None = None,
        max_concurrency: int = 2,
    ) -> "NoteGenerationPipeline":
        measured = _MeasuredLLMClient(client)
        semantic_analyzer = LLMSemanticAnalyzer(measured, max_concurrency=max_concurrency)
        knowledge_extractor = LLMKnowledgeExtractor(measured, max_concurrency=max_concurrency)
        pipeline = cls(
            semantic_analyzer,
            knowledge_extractor,
            event_handler=event_handler,
            measured_client=measured,
        )
        semantic_analyzer.set_progress_handler(
            lambda current, total, completed: pipeline._batch_event(
                "semantic", "Semantic chunks generated", current, total, completed
            )
        )
        knowledge_extractor.set_progress_handler(
            lambda current, total, completed: pipeline._batch_event(
                "knowledge", "Knowledge generated", current, total, completed
            )
        )
        semantic_analyzer.set_activity_handler(
            lambda operation, data: pipeline._llm_activity("semantic", operation, data)
        )
        knowledge_extractor.set_activity_handler(
            lambda operation, data: pipeline._llm_activity("knowledge", operation, data)
        )
        return pipeline

    def _llm_activity(
        self, stage: str, operation: str, data: dict[str, object]
    ) -> None:
        if operation == "retrying_validation" and self._measured_client:
            self._measured_client.retry_count += 1
        measured = self._measured_client
        progress = self._stage_progress.get(stage)
        activity = dict(data)
        active_batch = activity.pop("batch_current", None)
        batch_total = activity.pop("batch_total", None)
        batch_completed = None
        if progress is not None and isinstance(batch_total, int):
            batch_completed = round(progress * batch_total)
        self._event(
            stage,
            PipelineStatus.RUNNING,
            "Semantic chunks generated" if stage == "semantic" else "Knowledge generated",
            progress=progress,
            metrics={
                "operation": operation,
                "batch_completed": batch_completed,
                "batch_total": batch_total,
                "active_batch": active_batch,
                **activity,
                "llm_calls": measured.call_count if measured else None,
                "model": measured.last_model if measured else None,
                "input_tokens": measured.input_tokens if measured else None,
                "output_tokens": measured.output_tokens if measured else None,
            },
        )

    def _event(
        self, stage: str, status: PipelineStatus, message: str, **kwargs: Any
    ) -> None:
        self._emit(PipelineEvent(stage, status, message, **kwargs))

    def _batch_event(
        self,
        stage: str,
        message: str,
        current: int,
        total: int,
        completed: bool,
    ) -> None:
        """将业务模块的批次进度转换为统一 Pipeline 事件。"""

        completed_batches = current if completed else current - 1
        progress = completed_batches / total
        self._stage_progress[stage] = max(
            progress, self._stage_progress.get(stage, 0.0)
        )
        llm_calls = self._measured_client.call_count if self._measured_client else 0
        if not completed:
            llm_calls += 1
        measured_metrics: dict[str, Any] = {}
        if self._measured_client:
            measured_metrics = {
                "model": self._measured_client.last_model,
                "input_tokens": self._measured_client.input_tokens,
                "output_tokens": self._measured_client.output_tokens,
            }
        self._event(
            stage,
            PipelineStatus.RUNNING,
            message,
            progress=self._stage_progress[stage],
            metrics={
                "batch_completed": completed_batches,
                "batch_total": total,
                "llm_calls": llm_calls,
                "request_status": None if completed else "等待模型响应",
                **measured_metrics,
            },
        )

    async def run(
        self,
        source: str,
        output_path: str | Path,
        *,
        cookies_from_browser: str | None = "chrome",
        subtitle_language: str | None = None,
        subtitle_output_dir: Path = Path(".cache/noteforge/subtitles"),
        debug_dir: Path | None = None,
        precollected: VideoCollectionResult | None = None,
    ) -> Path:
        snapshots: dict[str, Any] = {}
        current_stage = "input"
        current_source_text: str | None = None
        started = perf_counter()

        async def async_stage(
            stage: str,
            message: str,
            operation: Any,
            metrics: Callable[[Any], dict[str, Any]] | None = None,
        ) -> Any:
            nonlocal current_stage
            current_stage = stage
            began = perf_counter()
            self._event(stage, PipelineStatus.RUNNING, message)
            result = await operation()
            self._event(
                stage,
                PipelineStatus.SUCCESS,
                message,
                metrics=metrics(result) if metrics else {},
                duration=perf_counter() - began,
            )
            return result

        def sync_stage(
            stage: str,
            message: str,
            operation: Any,
            metrics: Callable[[Any], dict[str, Any]] | None = None,
        ) -> Any:
            nonlocal current_stage
            current_stage = stage
            began = perf_counter()
            self._event(stage, PipelineStatus.RUNNING, message)
            result = operation()
            self._event(
                stage,
                PipelineStatus.SUCCESS,
                message,
                metrics=metrics(result) if metrics else {},
                duration=perf_counter() - began,
            )
            return result

        try:
            inspected = sync_stage("input", "Input validated", lambda: inspection.inspect_source(source))
            if inspected.platform is not inspection.InspectionPlatform.BILIBILI or inspected.normalized_source is None:
                raise UnsupportedSourceError(f"暂不支持该视频来源：{source}")

            collection = sync_stage(
                "transcript", "Transcript extracted",
                lambda: precollected or self._collector(
                    source=inspected.normalized_source,
                    cookies_from_browser=cookies_from_browser,
                    subtitle_language=subtitle_language,
                    subtitle_output_dir=subtitle_output_dir,
                    page_number=inspected.page_number,
                ),
                lambda result: {
                    "segments": (
                        len(result.transcript.segments) if result.transcript else 0
                    ),
                    "video_duration_minutes": (
                        round(result.metadata.duration / 60, 2)
                        if result.metadata.duration is not None
                        else None
                    ),
                },
            )
            if collection.transcript is None:
                raise NoteForgeError("视频没有可供处理的受支持字幕")

            raw_chunks = sync_stage(
                "chunk",
                "Raw chunks created",
                lambda: TranscriptChunker().chunk(collection.transcript),
                lambda result: {"raw_chunks": len(result)},
            )
            snapshots["raw_chunks.json"] = raw_chunks

            preprocessed_chunks = sync_stage(
                "preprocess",
                "Chunks preprocessed",
                lambda: ChunkPreprocessor().preprocess(raw_chunks),
                lambda result: {"preprocessed_chunks": len(result)},
            )

            semantic_chunks = await async_stage(
                "semantic",
                "Semantic chunks generated",
                lambda: self._semantic_analyzer.analyze(preprocessed_chunks),
                lambda result: {
                    "semantic_chunks": len(result),
                    "llm_calls": (
                        self._measured_client.call_count
                        if self._measured_client
                        else None
                    ),
                },
            )
            snapshots["semantic_chunks.json"] = semantic_chunks
            current_source_text = "\n".join(chunk.text for chunk in semantic_chunks)

            def knowledge_metrics(result: Any) -> dict[str, Any]:
                counts: dict[str, int] = {}
                for point in result:
                    counts[point.point_type.value] = (
                        counts.get(point.point_type.value, 0) + 1
                    )
                return {
                    "knowledge_points": len(result),
                    "types": counts,
                    "llm_calls": (
                        self._measured_client.call_count
                        if self._measured_client
                        else None
                    ),
                    "retries": (
                        self._measured_client.retry_count
                        if self._measured_client
                        else None
                    ),
                }

            knowledge_points = await async_stage(
                "knowledge",
                "Knowledge generated",
                lambda: self._knowledge_extractor.extract(semantic_chunks),
                knowledge_metrics,
            )
            if not knowledge_points:
                raise NoteForgeError("未能从视频字幕中提取出知识点")
            snapshots["knowledge_points.json"] = knowledge_points
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
