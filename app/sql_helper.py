from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from typing import List, Dict, Any


def get_engine(db_url: str) -> Engine:
    """Create and return a SQLAlchemy ``Engine`` for the given database URL.

    The URL should be in the form accepted by SQLAlchemy, e.g.:
        postgresql+psycopg2://user:password@host:5432/database
    """
    return create_engine(db_url)


def run_query(engine: Engine, sql: str, params: dict | None = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return the rows as a list of dictionaries.

    Parameters
    ----------
    engine: Engine
        The SQLAlchemy engine to use for the connection.
    sql: str
        The raw SQL statement (use ``:param`` placeholders for safe binding).
    params: dict | None
        Optional mapping of parameter names to values. If ``None`` an empty dict is used.
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = [dict(row._mapping) for row in result]
    return rows 
