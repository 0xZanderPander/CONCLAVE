from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from conclave.ledger.repository import LedgerRepository, create_schema


def create_test_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_schema(engine)
    return engine


def create_test_repository(engine: Engine) -> LedgerRepository:
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    return LedgerRepository(factory)
