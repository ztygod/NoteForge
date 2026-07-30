"""学习文档生成入口。"""

from noteforge.document.builder import KnowledgeDocumentBuilder
from noteforge.document.models import LearningDocument
from noteforge.knowledge.extraction.models import KnowledgePoint


def generate_document(
    knowledge_points: tuple[KnowledgePoint, ...],
) -> LearningDocument:
    """使用默认的规则构建器生成学习文档。"""

    return KnowledgeDocumentBuilder().build(knowledge_points)
