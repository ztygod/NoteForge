"""语义分析相关异常。"""

from noteforge.exceptions.base import NoteForgeError


class SemanticAnalysisError(NoteForgeError):
    """语义分析结果不合法。"""
