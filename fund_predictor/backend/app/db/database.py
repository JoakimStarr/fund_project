import sqlite3
import threading
from contextlib import contextmanager

from app.core.config import DB_PATH, ensure_dirs

_conn_local = threading.local()
_pool_lock = threading.Lock()


def _get_connection():
    if not hasattr(_conn_local, "conn") or _conn_local.conn is None:
        ensure_dirs()
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-64000")
        _init_schema(conn)
        _conn_local.conn = conn
    return _conn_local.conn


def _init_schema(conn: sqlite3.Connection) -> None:
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
    with _pool_lock:
        conn = _get_connection()
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_pool() -> None:
    if hasattr(_conn_local, "conn") and _conn_local.conn is not None:
        try:
            _conn_local.conn.close()
        except Exception:
            pass
        _conn_local.conn = None


def init_db() -> None:
    with get_conn() as conn:
        pass