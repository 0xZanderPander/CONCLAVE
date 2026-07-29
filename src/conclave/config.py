import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_ENVIRONMENT = "development"
DEFAULT_DATABASE_URL = "postgresql+psycopg://conclave:conclave@localhost:5432/conclave"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _integer(values: Mapping[str, str], name: str, default: int) -> int:
    value = int(values.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = DEFAULT_ENVIRONMENT
    database_url: str = DEFAULT_DATABASE_URL
    log_level: str = DEFAULT_LOG_LEVEL
    scheduler_interval_seconds: int = 60
    worker_idle_seconds: int = 2
    worker_lease_seconds: int = 300
    worker_retry_delay_seconds: int = 30
    worker_max_attempts: int = 3
    process_stale_after_seconds: int = 180
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_pool_timeout_seconds: int = 10
    database_pool_recycle_seconds: int = 1800
    caller_auth_mode: str = "local_fixture"
    caller_credentials_json: str | None = field(default=None, repr=False)
    reviewer_runtime_mode: str = "fixture"
    openai_api_key: str | None = field(default=None, repr=False)
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_base_url: str = DEFAULT_ANTHROPIC_BASE_URL
    google_api_key: str | None = field(default=None, repr=False)
    google_base_url: str = DEFAULT_GOOGLE_BASE_URL

    def __post_init__(self) -> None:
        if self.caller_auth_mode not in {"local_fixture", "static_bearer"}:
            raise ValueError("CONCLAVE_CALLER_AUTH_MODE is invalid")
        if (
            self.environment not in {"development", "test"}
            and self.caller_auth_mode == "local_fixture"
        ):
            raise ValueError(
                "non-local Conclave deployments require caller authentication"
            )
        if self.caller_auth_mode == "static_bearer" and not self.caller_credentials_json:
            raise ValueError(
                "static bearer authentication requires caller credentials"
            )
        if self.reviewer_runtime_mode not in {
            "fixture",
            "openai",
            "anthropic",
            "gemini",
            "multi_provider",
        }:
            raise ValueError("CONCLAVE_REVIEWER_RUNTIME_MODE is invalid")
        if (
            self.environment not in {"development", "test"}
            and self.reviewer_runtime_mode == "fixture"
        ):
            raise ValueError(
                "non-local Conclave deployments require a production reviewer runtime"
            )
        if self.reviewer_runtime_mode == "openai" and not self.openai_api_key:
            raise ValueError("the OpenAI reviewer runtime requires an API key")
        if self.reviewer_runtime_mode == "anthropic" and not self.anthropic_api_key:
            raise ValueError("the Anthropic reviewer runtime requires an API key")
        if self.reviewer_runtime_mode == "gemini" and not self.google_api_key:
            raise ValueError("the Gemini reviewer runtime requires a Google API key")
        if self.reviewer_runtime_mode == "multi_provider" and (
            not self.openai_api_key or not self.anthropic_api_key
        ):
            raise ValueError(
                "the multi-provider reviewer runtime requires OpenAI and Anthropic API keys"
            )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "Settings":
        values = environment if environment is not None else os.environ
        settings = cls(
            environment=values.get("CONCLAVE_ENVIRONMENT", DEFAULT_ENVIRONMENT),
            database_url=values.get("CONCLAVE_DATABASE_URL", DEFAULT_DATABASE_URL),
            log_level=values.get("CONCLAVE_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
            scheduler_interval_seconds=_integer(values, "CONCLAVE_SCHEDULER_INTERVAL_SECONDS", 60),
            worker_idle_seconds=_integer(values, "CONCLAVE_WORKER_IDLE_SECONDS", 2),
            worker_lease_seconds=_integer(values, "CONCLAVE_WORKER_LEASE_SECONDS", 300),
            worker_retry_delay_seconds=_integer(values, "CONCLAVE_WORKER_RETRY_DELAY_SECONDS", 30),
            worker_max_attempts=_integer(values, "CONCLAVE_WORKER_MAX_ATTEMPTS", 3),
            process_stale_after_seconds=_integer(
                values, "CONCLAVE_PROCESS_STALE_AFTER_SECONDS", 180
            ),
            database_pool_size=_integer(values, "CONCLAVE_DATABASE_POOL_SIZE", 5),
            database_max_overflow=_integer(values, "CONCLAVE_DATABASE_MAX_OVERFLOW", 5),
            database_pool_timeout_seconds=_integer(
                values, "CONCLAVE_DATABASE_POOL_TIMEOUT_SECONDS", 10
            ),
            database_pool_recycle_seconds=_integer(
                values, "CONCLAVE_DATABASE_POOL_RECYCLE_SECONDS", 1800
            ),
            caller_auth_mode=values.get(
                "CONCLAVE_CALLER_AUTH_MODE",
                "local_fixture",
            ),
            caller_credentials_json=values.get("CONCLAVE_CALLER_CREDENTIALS_JSON"),
            reviewer_runtime_mode=values.get(
                "CONCLAVE_REVIEWER_RUNTIME_MODE",
                "fixture",
            ),
            openai_api_key=values.get("CONCLAVE_OPENAI_API_KEY"),
            openai_base_url=values.get(
                "CONCLAVE_OPENAI_BASE_URL",
                DEFAULT_OPENAI_BASE_URL,
            ),
            anthropic_api_key=values.get("CONCLAVE_ANTHROPIC_API_KEY"),
            anthropic_base_url=values.get(
                "CONCLAVE_ANTHROPIC_BASE_URL",
                DEFAULT_ANTHROPIC_BASE_URL,
            ),
            google_api_key=values.get("CONCLAVE_GOOGLE_API_KEY"),
            google_base_url=values.get(
                "CONCLAVE_GOOGLE_BASE_URL",
                DEFAULT_GOOGLE_BASE_URL,
            ),
        )
        return settings
