from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread=False for the threaded dev server.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)

# Additive, idempotent column backfills for tables that predate a field. Keeps
# the dev SQLite DB (which holds real provisioned treasury wallets) intact
# rather than forcing a destructive recreate. Each entry is column -> DDL type.
# create_all already handles brand-new tables; this only patches existing ones.
_COLUMN_BACKFILLS: dict[str, dict[str, str]] = {
    "auditreview": {
        "evaluation_id": "VARCHAR",
        "recommendation": "VARCHAR",
        "overridden": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "escrowstate": {
        "lock_tx_hash": "VARCHAR",
        "settle_tx_hash": "VARCHAR",
        "custody_model": "VARCHAR NOT NULL DEFAULT 'custodial'",
        "controller_wallet": "VARCHAR",
    },
    "settlement": {
        "payout_tx_hash": "VARCHAR",
        "fee_basis": "VARCHAR",
    },
    "objective": {
        "agent_id": "VARCHAR",
    },
    "workspace": {
        "subscription_tier": "VARCHAR NOT NULL DEFAULT 'free'",
    },
}


def _backfill_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _COLUMN_BACKFILLS.items():
            if table not in existing_tables:
                continue  # create_all just made it with all columns
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))


def init_db() -> None:
    # Import models so SQLModel metadata is populated before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _backfill_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
