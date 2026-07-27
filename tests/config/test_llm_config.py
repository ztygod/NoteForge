import pytest

from noteforge.config import LLMSettings
from noteforge.config.llm import LLMSettings as DirectLLMSettings


def test_llm_settings_is_exported_from_config_package() -> None:
    assert LLMSettings is DirectLLMSettings


def test_llm_settings_requires_provider_and_model() -> None:
    with pytest.raises(ValueError, match="NOTEFORGE_LLM_PROVIDER"):
        LLMSettings.from_env({})

    with pytest.raises(ValueError, match="NOTEFORGE_LLM_MODEL"):
        LLMSettings.from_env({"NOTEFORGE_LLM_PROVIDER": "ollama"})
