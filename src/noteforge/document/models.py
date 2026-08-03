"""学习文档层的数据模型。"""

from dataclasses import dataclass

from noteforge.knowledge.extraction.models import KnowledgePoint


def _validate_non_empty_text(value: object, field_name: str) -> None:
    """校验必填文本已经由调用方规范化。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}不能为空")
    if value != value.strip():
        raise ValueError(f"{field_name}必须去除首尾空白")


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """学习文档中的一个章节，直接引用其包含的知识点。"""

    title: str
    description: str
    knowledge_points: tuple[KnowledgePoint, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.title, "DocumentSection 的标题")
        _validate_non_empty_text(
            self.description,
            "DocumentSection 的描述",
        )
        if not isinstance(self.knowledge_points, tuple):
            raise TypeError("DocumentSection 的 knowledge_points 必须是 tuple")
        if not self.knowledge_points:
            raise ValueError("DocumentSection 必须包含至少一个知识点")
        if not all(
            isinstance(point, KnowledgePoint)
            for point in self.knowledge_points
        ):
            raise TypeError(
                "DocumentSection 的 knowledge_points "
                "必须全部是 KnowledgePoint"
            )
        point_ids = tuple(id(point) for point in self.knowledge_points)
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("DocumentSection 不能重复引用同一个知识点")


@dataclass(frozen=True, slots=True)
class LearningDocument:
    """由多个章节组成的最终学习文档。"""

    title: str
    summary: str
    sections: tuple[DocumentSection, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.title, "LearningDocument 的标题")
        _validate_non_empty_text(self.summary, "LearningDocument 的摘要")
        if not isinstance(self.sections, tuple):
            raise TypeError("LearningDocument 的 sections 必须是 tuple")
        if not self.sections:
            raise ValueError("LearningDocument 必须包含至少一个章节")
        if not all(
            isinstance(section, DocumentSection)
            for section in self.sections
        ):
            raise TypeError(
                "LearningDocument 的 sections "
                "必须全部是 DocumentSection"
            )
