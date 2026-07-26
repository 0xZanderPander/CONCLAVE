import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_ENVIRONMENT = "development"
DEFAULT_DATABASE_URL = "postgresql+psycopg://conclave:conclave@localhost:5432/conclave"
DEFAULT_LOG_LEVEL = "INFO"


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

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "Settings":
        values = environment if environment is not None else os.environ
        return cls(
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
        )
