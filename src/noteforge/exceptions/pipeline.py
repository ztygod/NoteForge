"""向展示层提供包含上下文的 Pipeline 异常。"""

from dataclasses import dataclass

from noteforge.exceptions.base import NoteForgeError


@dataclass(frozen=True, slots=True)
class PipelineErrorContext:
    stage: str
    object_name: str | None = None
    reason: str | None = None
    allowed_values: tuple[str, ...] = ()
    source_text: str | None = None


class PipelineExecutionError(NoteForgeError):
    """使用面向用户的阶段上下文包装原始异常。"""

    def __init__(self, context: PipelineErrorContext, original: Exception):
        super().__init__(str(original))
        self.context = context
        self.original = original
