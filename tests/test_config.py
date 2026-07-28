import pytest

from conclave.config import Settings


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
