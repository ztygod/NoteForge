from pathlib import Path

from noteforge.config import (
    LLMSettings,
    merged_environment,
    read_dotenv,
    write_llm_dotenv,
)


def test_dotenv_round_trip_and_environment_precedence(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    write_llm_dotenv(
        {
            "NOTEFORGE_LLM_PROVIDER": "ollama",
            "NOTEFORGE_LLM_MODEL": "qwen2.5:7b",
            "NOTEFORGE_LLM_BASE_URL": "http://localhost:11434",
        },
        path,
    )

    assert read_dotenv(path)["NOTEFORGE_LLM_MODEL"] == "qwen2.5:7b"
    merged = merged_environment(
        {"NOTEFORGE_LLM_MODEL": "override"},
        dotenv_path=path,
    )
    assert merged["NOTEFORGE_LLM_MODEL"] == "override"


def test_write_dotenv_preserves_unrelated_values_and_is_private(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "OTHER_SETTING=keep\nNOTEFORGE_LLM_MODEL=old\n",
        encoding="utf-8",
    )

    write_llm_dotenv(
        {
            "NOTEFORGE_LLM_PROVIDER": "ollama",
            "NOTEFORGE_LLM_MODEL": "new",
        },
        path,
    )

    content = path.read_text(encoding="utf-8")
    assert "OTHER_SETTING=keep" in content
    assert "NOTEFORGE_LLM_MODEL=\"old\"" not in content
    assert read_dotenv(path)["NOTEFORGE_LLM_MODEL"] == "new"
    assert path.stat().st_mode & 0o077 == 0


def test_llm_settings_loads_dotenv_from_working_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "NOTEFORGE_LLM_PROVIDER=ollama\n"
        "NOTEFORGE_LLM_MODEL=local-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOTEFORGE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOTEFORGE_LLM_MODEL", raising=False)

    settings = LLMSettings.from_env()

    assert settings.provider == "ollama"
    assert settings.model == "local-model"
