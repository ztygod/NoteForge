"""从已校验的模型提案组装确定性的语义块。"""

from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.semantic.models import (
    SemanticChunk,
    SemanticChunkProposal,
)


def build_semantic_chunk(
    chunks: tuple[PreprocessedChunk, ...],
    proposal: SemanticChunkProposal,
) -> SemanticChunk:
    """只从来源块计算时间、文本和来源映射。"""

    source_chunks = tuple(chunks[index] for index in proposal.source_indexes)
    return SemanticChunk(
        start_time=source_chunks[0].start_time,
        end_time=source_chunks[-1].end_time,
        text="\n".join(chunk.text for chunk in source_chunks),
        topic=proposal.topic,
        summary=proposal.summary,
        chunk_type=proposal.chunk_type,
        importance=proposal.importance,
        source_chunks=source_chunks,
    )
