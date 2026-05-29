from collections.abc import Generator

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


def init_db() -> None:
    # Import models so SQLModel metadata is populated before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
