import sqlite3
from contextlib import contextmanager

from backend.app.core.config import DB_PATH, ensure_dirs


def init_db() -> None:
    ensure_dirs()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                fund_code TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT,
                error_details TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "error_details" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN error_details TEXT")
        conn.commit()


@contextmanager
def get_conn():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
