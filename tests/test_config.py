import pytest

from conclave.config import Settings
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.reviewers.factory import build_reviewer_runtime
from conclave.reviewers.runtime import ProviderRegistryRuntime


def test_settings_use_conclave_specific_environment_names() -> None:
    settings = Settings.from_environment(
        {
            "CONCLAVE_ENVIRONMENT": "test",
            "CONCLAVE_DATABASE_URL": "sqlite+pysqlite://",
            "CONCLAVE_LOG_LEVEL": "debug",
        }
    )

    assert settings.environment == "test"
    assert settings.database_url == "sqlite+pysqlite://"
    assert settings.log_level == "DEBUG"


def test_nonlocal_settings_require_explicit_caller_authentication() -> None:
    with pytest.raises(ValueError, match="require caller authentication"):
        Settings(environment="production")

    with pytest.raises(ValueError, match="requires caller credentials"):
        Settings(
            environment="production",
            caller_auth_mode="static_bearer",
        )


def test_production_reviewer_runtime_requires_an_explicit_provider() -> None:
    with pytest.raises(ValueError, match="production reviewer runtime"):
        Settings(
            environment="production",
            caller_auth_mode="static_bearer",
            caller_credentials_json='{"caller":{"token":"secret","scopes":[]}}',
        )

    with pytest.raises(ValueError, match="requires an API key"):
        Settings(reviewer_runtime_mode="openai")

    with pytest.raises(ValueError, match="Anthropic reviewer runtime"):
        Settings(reviewer_runtime_mode="anthropic")

    with pytest.raises(ValueError, match="Google API key"):
        Settings(reviewer_runtime_mode="gemini")

    with pytest.raises(ValueError, match="OpenAI and Anthropic"):
        Settings(
            reviewer_runtime_mode="multi_provider",
            openai_api_key="test-openai-key",
        )


def test_reviewer_runtime_factory_never_silently_falls_back() -> None:
    fixture = build_reviewer_runtime(Settings())
    production = build_reviewer_runtime(
        Settings(
            reviewer_runtime_mode="openai",
            openai_api_key="test-key",
        )
    )

    assert isinstance(fixture, DevelopmentReviewerRuntime)
    assert isinstance(production, ProviderRegistryRuntime)


def test_multi_provider_runtime_registers_both_explicit_adapters() -> None:
    runtime = build_reviewer_runtime(
        Settings(
            reviewer_runtime_mode="multi_provider",
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )
    )

    assert isinstance(runtime, ProviderRegistryRuntime)


def test_gemini_runtime_requires_and_registers_its_explicit_adapter() -> None:
    settings = Settings.from_environment(
        {
            "CONCLAVE_REVIEWER_RUNTIME_MODE": "gemini",
            "CONCLAVE_GOOGLE_API_KEY": "test-google-key",
            "CONCLAVE_GOOGLE_BASE_URL": "https://google.test/v1beta",
        }
    )

    assert settings.google_api_key == "test-google-key"
    assert settings.google_base_url == "https://google.test/v1beta"
    assert isinstance(build_reviewer_runtime(settings), ProviderRegistryRuntime)
