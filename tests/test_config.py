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
