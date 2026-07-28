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
