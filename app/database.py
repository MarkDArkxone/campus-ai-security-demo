from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BASE_DIR, DATABASE_URL, SNAPSHOT_DIR


BASE_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()


def ensure_schema_columns() -> None:
    """Lightweight SQLite schema repair for demo machines with an older db file.

    SQLAlchemy's create_all creates missing tables but does not add columns to
    tables that already exist. For a classroom demo that may be copied between
    machines, adding missing nullable columns is safer than asking users to
    delete their database.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns or column.primary_key:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
