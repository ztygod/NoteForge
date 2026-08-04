"""configure 子命令及首次配置逻辑。"""

from pathlib import Path
import sys

import typer

from noteforge.config import LLMSettings, read_dotenv, write_llm_dotenv
from noteforge.exceptions import LLMConfigurationError


_API_FORMAT_DEFAULTS = {
    "ollama": ("qwen2.5:7b", "http://localhost:11434"),
    "openai": ("", "https://api.openai.com/v1"),
    "anthropic": ("", "https://api.anthropic.com/v1"),
}


def prompt_api_format(default: str = "ollama") -> str:
    """提示用户选择模型端点使用的 API 格式。"""

    while True:
        api_format = typer.prompt(
            "LLM API 格式（ollama/openai/anthropic）",
            default=default,
        ).strip().lower()
        if api_format in _API_FORMAT_DEFAULTS:
            return api_format
        typer.secho(
            "请输入 ollama、openai 或 anthropic；它们表示 API 格式。",
            fg=typer.colors.YELLOW,
            err=True,
        )


def run_configuration_wizard(path: Path = Path(".env")) -> LLMSettings:
    """交互收集、校验并保存 LLM 配置。"""

    existing = read_dotenv(path)
    existing_api_format = existing.get(
        "NOTEFORGE_LLM_PROVIDER", "ollama"
    ).strip().lower()
    if existing_api_format not in _API_FORMAT_DEFAULTS:
        existing_api_format = "ollama"

    typer.echo(
        "欢迎使用 NoteForge！先完成一次 LLM 配置。\n"
        "如果使用 Ollama，请确保服务已经启动并已下载所选模型。"
    )
    api_format = prompt_api_format(existing_api_format)
    default_model, default_base_url = _API_FORMAT_DEFAULTS[api_format]
    model = typer.prompt(
        "模型名称",
        default=existing.get("NOTEFORGE_LLM_MODEL") or default_model or None,
    ).strip()
    while not model:
        typer.secho("模型名称不能为空。", fg=typer.colors.YELLOW, err=True)
        model = typer.prompt("模型名称").strip()

    api_key = ""
    if api_format in {"openai", "anthropic"}:
        existing_key = existing.get("NOTEFORGE_LLM_API_KEY", "")
        if existing_key and typer.confirm("保留现有 API Key？", default=True):
            api_key = existing_key
        else:
            api_key = typer.prompt("API Key", hide_input=True).strip()
            while not api_key:
                typer.secho(
                    "该 API 格式需要 API Key。",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                api_key = typer.prompt("API Key", hide_input=True).strip()

    base_url = typer.prompt(
        "接口地址",
        default=existing.get("NOTEFORGE_LLM_BASE_URL") or default_base_url,
    ).strip()
    timeout = typer.prompt(
        "请求超时（秒）",
        default=existing.get("NOTEFORGE_LLM_TIMEOUT_SECONDS", "120"),
    ).strip()

    values = {
        # 环境变量名为兼容 0.1 保留，值实际表示 API 格式。
        "NOTEFORGE_LLM_PROVIDER": api_format,
        "NOTEFORGE_LLM_MODEL": model,
        "NOTEFORGE_LLM_BASE_URL": base_url,
        "NOTEFORGE_LLM_TIMEOUT_SECONDS": timeout,
    }
    if api_key:
        values["NOTEFORGE_LLM_API_KEY"] = api_key

    try:
        settings = LLMSettings.from_env(values)
    except ValueError as error:
        typer.secho(f"配置无效：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    written_path = write_llm_dotenv(values, path)
    typer.secho(
        f"配置已保存到 {written_path}（权限仅限当前用户）。",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "可以运行 `noteforge doctor` 检查服务和模型，或运行\n"
        "`noteforge doctor <视频URL>` 同时检查 Cookie 与字幕。"
    )
    return settings


def load_configured_llm_settings() -> LLMSettings:
    """加载配置，并在交互终端中引导用户补齐缺失项。"""

    try:
        return LLMSettings.from_env()
    except ValueError as error:
        configuration_error = LLMConfigurationError(str(error))
        if not sys.stdin.isatty():
            raise LLMConfigurationError(
                f"{configuration_error}；请先运行 `noteforge configure`。"
            ) from error
        typer.secho(
            f"尚未完成 LLM 配置：{configuration_error}",
            fg=typer.colors.YELLOW,
        )
        if not typer.confirm("现在开始配置？", default=True):
            raise LLMConfigurationError(
                "尚未配置 LLM；请先运行 `noteforge configure`。"
            ) from error
        return run_configuration_wizard()


def configure(
    path: Path = typer.Option(
        Path(".env"),
        "--path",
        help="保存 NoteForge 环境变量的 dotenv 文件。",
    ),
) -> None:
    """交互设置 LLM 环境变量，首次使用时建议先运行。"""

    run_configuration_wizard(path)
