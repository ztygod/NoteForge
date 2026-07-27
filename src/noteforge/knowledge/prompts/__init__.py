"""NoteForge 知识任务 Prompt 模板。"""

from noteforge.knowledge.prompts.base import BasePrompt
from noteforge.knowledge.prompts.chunk_analysis import ChunkAnalysisPrompt
from noteforge.knowledge.prompts.concept_extraction import (
    ConceptExtractionPrompt,
)
from noteforge.knowledge.prompts.semantic_analysis import (
    SemanticAnalysisPrompt,
)

__all__ = [
    "BasePrompt",
    "ChunkAnalysisPrompt",
    "ConceptExtractionPrompt",
    "SemanticAnalysisPrompt",
]
