"""NoteForge 配置包。

具体领域配置拆分在独立模块中，并从这里导出稳定的公共接口。
"""

from noteforge.config.dotenv import (
    DEFAULT_ENV_PATH,
    merged_environment,
    read_dotenv,
    write_llm_dotenv,
)
from noteforge.config.llm import LLMSettings
from noteforge.config.llm import llm_api_format_label

__all__ = [
    "DEFAULT_ENV_PATH",
    "LLMSettings",
    "llm_api_format_label",
    "merged_environment",
    "read_dotenv",
    "write_llm_dotenv",
]
