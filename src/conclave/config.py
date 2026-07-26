import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_ENVIRONMENT = "development"
DEFAULT_DATABASE_URL = "postgresql+psycopg://conclave:conclave@localhost:5432/conclave"
DEFAULT_LOG_LEVEL = "INFO"


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = DEFAULT_ENVIRONMENT
    database_url: str = DEFAULT_DATABASE_URL
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "Settings":
        values = environment if environment is not None else os.environ
        return cls(
            environment=values.get("CONCLAVE_ENVIRONMENT", DEFAULT_ENVIRONMENT),
            database_url=values.get("CONCLAVE_DATABASE_URL", DEFAULT_DATABASE_URL),
            log_level=values.get("CONCLAVE_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
        )
