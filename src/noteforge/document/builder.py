"""使用确定性规则将知识点组织成学习文档。"""

from dataclasses import dataclass

from noteforge.document.models import DocumentSection, LearningDocument
from noteforge.knowledge.extraction.models import (
    KnowledgePoint,
    KnowledgePointType,
)


@dataclass(frozen=True, slots=True)
class _SectionDefinition:
    """一种知识点类型对应的章节元数据。"""

    title: str
    description: str


_SECTION_ORDER = (
    KnowledgePointType.CONCEPT,
    KnowledgePointType.PRINCIPLE,
    KnowledgePointType.PROCEDURE,
    KnowledgePointType.EXAMPLE,
    KnowledgePointType.COMPARISON,
    KnowledgePointType.OTHER,
)

_SECTION_DEFINITIONS = {
    KnowledgePointType.CONCEPT: _SectionDefinition(
        "基础概念",
        "介绍学习主题中的基础概念与定义。",
    ),
    KnowledgePointType.PRINCIPLE: _SectionDefinition(
        "核心原理",
        "说明相关机制、规律与核心原理。",
    ),
    KnowledgePointType.PROCEDURE: _SectionDefinition(
        "工作流程",
        "梳理需要依次理解或执行的流程。",
    ),
    KnowledgePointType.EXAMPLE: _SectionDefinition(
        "示例解析",
        "通过具体示例帮助理解和应用知识。",
    ),
    KnowledgePointType.COMPARISON: _SectionDefinition(
        "对比分析",
        "对相关概念、方案或特征进行比较。",
    ),
    KnowledgePointType.OTHER: _SectionDefinition(
        "其他知识",
        "收录未归入主要章节的补充知识。",
    ),
}

_DIRECT_SECTION_TYPES = frozenset(_SECTION_ORDER[:-1])


class KnowledgeDocumentBuilder:
    """按知识点类型构建结构稳定的学习文档。"""

    def build(
        self,
        knowledge_points: tuple[KnowledgePoint, ...],
    ) -> LearningDocument:
        """将一组知识点分类并组织为学习文档。"""

        self._validate_input(knowledge_points)
        grouped: dict[KnowledgePointType, list[KnowledgePoint]] = {
            point_type: [] for point_type in _SECTION_ORDER
        }
        for point in knowledge_points:
            section_type = (
                point.point_type
                if point.point_type in _DIRECT_SECTION_TYPES
                else KnowledgePointType.OTHER
            )
            grouped[section_type].append(point)

        sections = tuple(
            self._build_section(point_type, tuple(grouped[point_type]))
            for point_type in _SECTION_ORDER
            if grouped[point_type]
        )
        subject = self._infer_subject(knowledge_points)
        section_titles = "、".join(section.title for section in sections)
        return LearningDocument(
            title=f"{subject}学习笔记",
            summary=(
                f"本文档整理了 {len(knowledge_points)} 个知识点，"
                f"涵盖{section_titles}。"
            ),
            sections=sections,
        )

    @staticmethod
    def _validate_input(
        knowledge_points: tuple[KnowledgePoint, ...],
    ) -> None:
        """拒绝无法形成有效文档的输入。"""

        if not isinstance(knowledge_points, tuple):
            raise TypeError("knowledge_points 必须是 tuple")
        if not knowledge_points:
            raise ValueError("knowledge_points 不能为空")
        if not all(
            isinstance(point, KnowledgePoint) for point in knowledge_points
        ):
            raise TypeError("knowledge_points 必须全部是 KnowledgePoint")

    @staticmethod
    def _build_section(
        point_type: KnowledgePointType,
        points: tuple[KnowledgePoint, ...],
    ) -> DocumentSection:
        """根据固定元数据创建一个章节。"""

        definition = _SECTION_DEFINITIONS[point_type]
        return DocumentSection(
            title=definition.title,
            description=definition.description,
            knowledge_points=points,
        )

    @staticmethod
    def _infer_subject(
        knowledge_points: tuple[KnowledgePoint, ...],
    ) -> str:
        """选择最高频关键词作为主题，同频时保留首次出现顺序。"""

        keyword_counts: dict[str, int] = {}
        for point in knowledge_points:
            for keyword in point.keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        if not keyword_counts:
            return knowledge_points[0].title
        return max(keyword_counts, key=lambda keyword: keyword_counts[keyword])
