"""Prompt 模板的统一接口。"""

from abc import ABC
import re
from typing import ClassVar, Mapping

from noteforge.knowledge.prompts.utils import stringify_prompt_value
from noteforge.llm.models import LLMMessage


_VARIABLE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class BasePrompt(ABC):
    """所有 Prompt 模板的共同基类。

    子类只需声明 system/user 模板。变量替换使用显式字段，不执行表达式，
    从而让模板内容保持可审查、可测试。
    """

    system_template: ClassVar[str]
    user_template: ClassVar[str]

    def build_system_prompt(
        self,
        variables: Mapping[str, object] | None = None,
    ) -> str:
        """构建 system prompt。"""

        return self._render(self.system_template, variables or {})

    def build_user_prompt(
        self,
        variables: Mapping[str, object],
    ) -> str:
        """注入输入变量并构建 user prompt。"""

        return self._render(self.user_template, variables)

    def build_messages(
        self,
        variables: Mapping[str, object],
    ) -> tuple[LLMMessage, LLMMessage]:
        """构建可直接交给 LLM Client 的消息，但不执行模型调用。"""

        return (
            LLMMessage(
                role="system",
                content=self.build_system_prompt(variables),
            ),
            LLMMessage(
                role="user",
                content=self.build_user_prompt(variables),
            ),
        )

    @staticmethod
    def _render(template: str, variables: Mapping[str, object]) -> str:
        fields = set(_VARIABLE_PATTERN.findall(template))
        missing = fields.difference(variables)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Prompt 缺少变量：{names}")

        rendered_variables = {
            name: stringify_prompt_value(value)
            for name, value in variables.items()
        }
        return _VARIABLE_PATTERN.sub(
            lambda match: rendered_variables[match.group(1)],
            template,
        ).strip()
