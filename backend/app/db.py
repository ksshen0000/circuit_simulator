import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "./circuit.db")

# Bump this when the schema changes and append the corresponding migration below.
SCHEMA_VERSION = 1

# _MIGRATIONS[i] upgrades the database from version i to version i + 1.
_MIGRATIONS: list[str] = [
    # v0 -> v1: initial schema
    """
    CREATE TABLE IF NOT EXISTS circuits (
        id                TEXT PRIMARY KEY,
        name              TEXT NOT NULL,
        elements          TEXT NOT NULL,
        wires             TEXT NOT NULL,
        ground_element_id TEXT,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL
    )
    """,
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than the supported {SCHEMA_VERSION}"
            )
        for target in range(version, SCHEMA_VERSION):
            conn.execute(_MIGRATIONS[target])
        if version != SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
