import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "./circuit.db")

# Bump this when the schema changes and append the corresponding migration below.
SCHEMA_VERSION = 2

# _MIGRATIONS[i] upgrades the database from version i to version i + 1.
# Each migration is a list of single SQL statements.
_MIGRATIONS: list[list[str]] = [
    # v0 -> v1: initial schema
    [
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
    ],
    # v1 -> v2: projects and circuit ownership
    [
        """
        CREATE TABLE IF NOT EXISTS projects (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        "ALTER TABLE circuits ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE SET NULL",
    ],
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from .seed import seed_examples

    conn = _connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than the supported {SCHEMA_VERSION}"
            )
        for target in range(version, SCHEMA_VERSION):
            for statement in _MIGRATIONS[target]:
                conn.execute(statement)
        if version != SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("PRAGMA journal_mode=WAL")
        seed_examples(conn)
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
