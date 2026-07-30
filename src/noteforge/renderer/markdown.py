"""将学习文档渲染为 Markdown。"""

import re

from noteforge.document import LearningDocument
from noteforge.knowledge.extraction import KnowledgePoint


_MARKDOWN_SPECIAL_CHARACTERS = re.compile(r"([\\`*_{}\[\]()#+.!|>\-])")


def _escape_markdown(text: str) -> str:
    """转义作为 Markdown 结构内容使用的特殊字符。"""

    return _MARKDOWN_SPECIAL_CHARACTERS.sub(r"\\\1", text)


def _format_time(value: float) -> str:
    """以紧凑且稳定的形式输出秒数。"""

    return format(value, "g")


class MarkdownRenderer:
    """将只读的 ``LearningDocument`` 转换为 Markdown 文本。"""

    def render(self, document: LearningDocument) -> str:
        """按文档和知识点的原有顺序渲染 Markdown。"""

        if not isinstance(document, LearningDocument):
            raise TypeError("document 必须是 LearningDocument")

        lines = [
            f"# {_escape_markdown(document.title)}",
            "",
            self._render_summary(document.summary),
        ]
        for section in document.sections:
            lines.extend(("", f"## {_escape_markdown(section.title)}"))
            for point in section.knowledge_points:
                lines.extend(("", self._render_knowledge_point(point)))
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_summary(summary: str) -> str:
        """将单行或多行摘要渲染为引用块。"""

        return "\n".join(
            f"> {_escape_markdown(line)}" if line else ">"
            for line in summary.splitlines()
        )

    @staticmethod
    def _render_knowledge_point(point: KnowledgePoint) -> str:
        """渲染一个知识点及其元数据。"""

        keywords = (
            "\n".join(
                f"- {_escape_markdown(keyword)}"
                for keyword in point.keywords
            )
            if point.keywords
            else "（无）"
        )
        return "\n".join(
            (
                f"### {_escape_markdown(point.title)}",
                "",
                point.explanation,
                "",
                "类型:",
                "",
                _escape_markdown(point.point_type.value),
                "",
                "关键词:",
                "",
                keywords,
                "",
                "来源:",
                "",
                (
                    f"{_format_time(point.start_time)} - "
                    f"{_format_time(point.end_time)}"
                ),
                "",
                "---",
            )
        )
