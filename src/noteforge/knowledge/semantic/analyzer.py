"""基于统一 LLM Client 的批量语义分析器。"""

from collections.abc import Callable
from typing import Protocol

from noteforge.exceptions import LLMJSONDecodeError, SemanticAnalysisError
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.prompts import SemanticAnalysisPrompt
from noteforge.knowledge.semantic.builder import build_semantic_chunk
from noteforge.knowledge.semantic.models import SemanticChunk
from noteforge.knowledge.semantic.validation import (
    parse_semantic_analysis_result,
    validate_semantic_analysis_result,
)
from noteforge.llm import LLMClient, LLMRequestOptions


class SemanticAnalyzer(Protocol):
    """PreprocessedChunk 到 SemanticChunk 的异步接口。"""

    async def analyze(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        """分析一批连续预处理块。"""


class LLMSemanticAnalyzer:
    """将批处理、模型调用、校验和确定性组装串联起来。"""

    def __init__(
        self,
        client: LLMClient,
        *,
        batch_size: int = 20,
        prompt: SemanticAnalysisPrompt | None = None,
        progress_handler: Callable[[int, int, bool], None] | None = None,
    ) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size <= 0
        ):
            raise ValueError("batch_size 必须是正整数")
        self._client = client
        self._batch_size = batch_size
        self._prompt = prompt or SemanticAnalysisPrompt()
        self._progress_handler = progress_handler

    def set_progress_handler(
        self,
        handler: Callable[[int, int, bool], None],
    ) -> None:
        """绑定批次进度处理器，参数依次为当前批次、总批次和是否完成。"""

        self._progress_handler = handler

    async def analyze(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        if not isinstance(chunks, tuple) or not all(
            isinstance(chunk, PreprocessedChunk) for chunk in chunks
        ):
            raise TypeError("chunks 必须是 PreprocessedChunk 元组")
        results: list[SemanticChunk] = []
        total_batches = (len(chunks) + self._batch_size - 1) // self._batch_size
        for batch_number, start in enumerate(
            range(0, len(chunks), self._batch_size),
            start=1,
        ):
            batch = chunks[start : start + self._batch_size]
            if self._progress_handler:
                self._progress_handler(batch_number, total_batches, False)
            results.extend(await self._analyze_batch(batch))
            if self._progress_handler:
                self._progress_handler(batch_number, total_batches, True)
        return tuple(results)

    async def _analyze_batch(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        """分析单批输入；批次策略可独立替换为 token 预算策略。"""

        if not chunks:
            return ()
        messages = self._prompt.build_for_chunks(chunks)
        try:
            raw_result = self._client.generate_json(
                messages,
                options=LLMRequestOptions(temperature=0),
            )
        except LLMJSONDecodeError as error:
            raise SemanticAnalysisError(
                "Semantic analysis model returned invalid JSON"
            ) from error
        result = parse_semantic_analysis_result(raw_result)
        validate_semantic_analysis_result(result, len(chunks))
        return tuple(
            build_semantic_chunk(chunks, proposal)
            for proposal in result.semantic_chunks
        )
