from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread=False for the threaded dev server.
_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# On managed/serverless Postgres (Neon) the compute auto-suspends when idle, so
# a pooled connection can be silently dropped between requests — the first query
# after a lull then raises OperationalError (sqlalche.me/e/20/e3q8). pool_pre_ping
# issues a lightweight liveness check and transparently reconnects; pool_recycle
# proactively retires connections before Neon's idle timeout closes them.
_pg_kwargs = {} if _is_sqlite else {"pool_pre_ping": True, "pool_recycle": 280}

engine = create_engine(
    settings.database_url, echo=False, connect_args=connect_args, **_pg_kwargs
)

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
        "role_id": "VARCHAR",
    },
    "objective": {
        "agent_id": "VARCHAR",
        "definition_of_done": "VARCHAR",
        "deadline": "VARCHAR",
    },
    "agentidentity": {
        "description": "VARCHAR",
        "pricing": "VARCHAR",
        "discoverable": "BOOLEAN NOT NULL DEFAULT 1",
        "pricing_model": "VARCHAR NOT NULL DEFAULT 'fixed'",
        "min_objective_value_usdc": "VARCHAR",
        "min_role_compensation_usdc": "VARCHAR",
        "availability": "VARCHAR NOT NULL DEFAULT 'available'",
        "max_concurrent": "INTEGER NOT NULL DEFAULT 5",
        # Escrow V1.5 — payout destination + proof-of-control state.
        "payout_address": "VARCHAR",
        "payout_blockchain": "VARCHAR",
        "payout_address_verified": "BOOLEAN NOT NULL DEFAULT 0",
        "payout_address_verified_at": "DATETIME",
        "payout_challenge": "VARCHAR",
        "payout_challenge_address": "VARCHAR",
        "payout_challenge_expires_at": "DATETIME",
    },
    "workspace": {
        "subscription_tier": "VARCHAR NOT NULL DEFAULT 'free'",
        # Existing workspaces are already operational, so backfill them as
        # completed (DEFAULT 1). Brand-new rows inserted by SQLModel use the
        # model default (False) and are routed through onboarding.
        "onboarding_completed": "BOOLEAN NOT NULL DEFAULT 1",
        "governance_require_auditor": "BOOLEAN NOT NULL DEFAULT 1",
        "governance_human_authoritative": "BOOLEAN NOT NULL DEFAULT 1",
    },
    "workflowrole": {
        "outcome": "VARCHAR",
        "depends_on": "JSON NOT NULL DEFAULT '[]'",
        "success_criteria": "JSON NOT NULL DEFAULT '[]'",
        "required_evidence_kinds": "JSON NOT NULL DEFAULT '[]'",
        "required": "BOOLEAN NOT NULL DEFAULT 1",
        "validation_status": "VARCHAR NOT NULL DEFAULT 'pending'",
        "settlement_status": "VARCHAR NOT NULL DEFAULT 'pending'",
    },
    "validationrecord": {
        "role_id": "VARCHAR",
    },
    "settlementauthorization": {
        "role_id": "VARCHAR",
    },
    "governanceevaluation": {
        "role_id": "VARCHAR",
        "risks": "JSON NOT NULL DEFAULT '[]'",
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
