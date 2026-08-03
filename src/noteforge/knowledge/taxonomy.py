"""跨知识处理阶段共享的类型体系。"""

from enum import StrEnum


class SemanticChunkType(StrEnum):
    """输入内容在讲述过程中的语义角色。"""

    DEFINITION = "definition"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    COMPARISON = "comparison"
    PROCEDURE = "procedure"
    CONCLUSION = "conclusion"
    TRANSITION = "transition"
    QUESTION = "question"
    OTHER = "other"


class KnowledgePointType(StrEnum):
    """最终笔记中一个知识点的知识分类。"""

    CONCEPT = "concept"
    PRINCIPLE = "principle"
    PROCEDURE = "procedure"
    API = "api"
    EXAMPLE = "example"
    COMPARISON = "comparison"
    PITFALL = "pitfall"
    CONCLUSION = "conclusion"
    OTHER = "other"
