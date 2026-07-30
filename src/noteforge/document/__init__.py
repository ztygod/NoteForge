"""将知识点组织成结构化学习文档。"""

from noteforge.document.builder import KnowledgeDocumentBuilder
from noteforge.document.generator import generate_document
from noteforge.document.models import DocumentSection, LearningDocument

__all__ = [
    "DocumentSection",
    "KnowledgeDocumentBuilder",
    "LearningDocument",
    "generate_document",
]
