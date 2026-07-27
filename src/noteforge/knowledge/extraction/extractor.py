"""基于统一 LLM Client 的批量知识点提取器。"""

from typing import Protocol

from noteforge.exceptions import (
    KnowledgeExtractionError,
    LLMJSONDecodeError,
)
from noteforge.knowledge.extraction.builder import build_knowledge_point
from noteforge.knowledge.extraction.models import KnowledgePoint
from noteforge.knowledge.extraction.validation import (
    parse_knowledge_extraction_result,
    validate_knowledge_proposals,
)
from noteforge.knowledge.prompts import KnowledgeExtractionPrompt
from noteforge.knowledge.semantic.models import SemanticChunk
from noteforge.llm import LLMClient, LLMRequestOptions


class KnowledgeExtractor(Protocol):
    """从语义块中提取知识点。"""

    async def extract(
        self,
        chunks: tuple[SemanticChunk, ...],
    ) -> tuple[KnowledgePoint, ...]:
        """提取一批连续语义块中的知识点。"""


class LLMKnowledgeExtractor:
    """调用大语言模型提取知识点，并由程序恢复来源映射。"""

    def __init__(
        self,
        client: LLMClient,
        *,
        batch_size: int = 20,
        prompt: KnowledgeExtractionPrompt | None = None,
    ) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size <= 0
        ):
            raise ValueError("batch_size 必须是正整数")
        self._client = client
        self._batch_size = batch_size
        self._prompt = prompt or KnowledgeExtractionPrompt()

    async def extract(
        self,
        chunks: tuple[SemanticChunk, ...],
    ) -> tuple[KnowledgePoint, ...]:
        if not isinstance(chunks, tuple) or not all(
            isinstance(chunk, SemanticChunk) for chunk in chunks
        ):
            raise TypeError("chunks 必须是 SemanticChunk 元组")

        results: list[KnowledgePoint] = []
        for start_index in range(0, len(chunks), self._batch_size):
            batch = chunks[start_index : start_index + self._batch_size]
            results.extend(
                await self._extract_batch(
                    batch,
                    start_index=start_index,
                    all_chunks=chunks,
                )
            )
        return tuple(results)

    async def _extract_batch(
        self,
        chunks: tuple[SemanticChunk, ...],
        *,
        start_index: int = 0,
        all_chunks: tuple[SemanticChunk, ...] | None = None,
    ) -> tuple[KnowledgePoint, ...]:
        """提取单批知识点。

        当前知识点只能引用同一批次内的语义块；跨批次合并留给后续的
        overlap window 或二次归并阶段。
        """

        if not chunks:
            return ()
        source_chunks = all_chunks if all_chunks is not None else chunks
        messages = self._prompt.build_for_chunks(
            chunks,
            start_index=start_index,
        )
        try:
            raw_result = self._client.generate_json(
                messages,
                options=LLMRequestOptions(temperature=0),
            )
        except LLMJSONDecodeError as error:
            raise KnowledgeExtractionError(
                "Knowledge extraction model returned invalid JSON"
            ) from error
        except Exception as error:
            raise KnowledgeExtractionError(
                f"Knowledge extraction model request failed: {error}"
            ) from error

        result = parse_knowledge_extraction_result(raw_result)
        validate_knowledge_proposals(
            result.knowledge_points,
            len(source_chunks),
        )
        batch_end = start_index + len(chunks)
        for position, proposal in enumerate(result.knowledge_points):
            if any(
                index < start_index or index >= batch_end
                for index in proposal.source_indexes
            ):
                raise KnowledgeExtractionError(
                    f"Knowledge point {position} references source index "
                    "outside the current batch"
                )

        # Python 的排序是稳定的，同一首索引保持模型返回顺序。
        ordered_proposals = sorted(
            result.knowledge_points,
            key=lambda proposal: proposal.source_indexes[0],
        )
        return tuple(
            build_knowledge_point(source_chunks, proposal)
            for proposal in ordered_proposals
        )
