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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fund_profiles (
            fund_code       TEXT PRIMARY KEY,
            fund_name       TEXT NOT NULL DEFAULT '',
            fund_type       TEXT NOT NULL DEFAULT 'unknown',
            fund_type_raw   TEXT DEFAULT '',
            establish_date  TEXT,
            fund_size       REAL,
            manager         TEXT DEFAULT '',
            fee_rate        REAL,
            benchmark       TEXT DEFAULT '',
            strategy_text   TEXT DEFAULT '',
            strategy_keywords TEXT DEFAULT '',
            skip_prediction INTEGER DEFAULT 0,
            risk_level      TEXT DEFAULT '',
            data_source     TEXT DEFAULT 'akshare',
            fetched_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            cache_ttl_days  INTEGER DEFAULT 7,
            raw_info_json   TEXT DEFAULT '',
            asset_allocation_json TEXT DEFAULT '',
            industry_distribution_json TEXT DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_profiles_type ON fund_profiles(fund_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_profiles_name ON fund_profiles(fund_name)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fund_nav (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code       TEXT NOT NULL,
            trade_date      TEXT NOT NULL,
            nav             REAL NOT NULL,
            acc_nav         REAL,
            daily_growth_pct REAL,
            source          TEXT DEFAULT 'unknown',
            UNIQUE(fund_code, trade_date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_nav_code_date ON fund_nav(fund_code, trade_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_nav_date ON fund_nav(trade_date)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS index_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            index_name      TEXT NOT NULL,
            symbol          TEXT NOT NULL,
            trade_date      TEXT NOT NULL,
            open            REAL,
            high            REAL,
            low             REAL,
            close           REAL NOT NULL,
            volume          REAL,
            amount          REAL,
            source          TEXT DEFAULT 'eastmoney',
            UNIQUE(index_name, trade_date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_index_data_name_date ON index_data(index_name, trade_date)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS holdings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code       TEXT NOT NULL,
            report_date     TEXT NOT NULL,
            stock_code      TEXT NOT NULL,
            stock_name      TEXT DEFAULT '',
            weight_pct      REAL,
            market_cap      REAL,
            sector          TEXT DEFAULT '',
            UNIQUE(fund_code, report_date, stock_code)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_holdings_fund_date ON holdings(fund_code, report_date)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS train_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         TEXT NOT NULL UNIQUE,
            fund_code       TEXT NOT NULL,
            model_version   TEXT DEFAULT '',
            model_type      TEXT DEFAULT '',
            metrics_json    TEXT DEFAULT '',
            features_json   TEXT DEFAULT '',
            model_path      TEXT DEFAULT '',
            backtest_path   TEXT DEFAULT '',
            status          TEXT DEFAULT 'success',
            created_at      TEXT NOT NULL,
            training_duration_secs REAL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_train_results_fund ON train_results(fund_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_train_results_created ON train_results(created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_fetch_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type     TEXT NOT NULL,
            entity_key      TEXT NOT NULL,
            source          TEXT NOT NULL,
            success         INTEGER NOT NULL DEFAULT 0,
            rows_affected   INTEGER DEFAULT 0,
            error_message   TEXT,
            duration_ms     INTEGER,
            fetched_at      TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fetch_log_entity ON data_fetch_log(entity_type, entity_key, fetched_at)")

    # ★ AI 分析缓存表（v2.6.0 新增）
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_cache (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code       TEXT NOT NULL,
            trade_date      TEXT NOT NULL,
            source          TEXT NOT NULL,
            analysis_json   TEXT NOT NULL,
            provider_used   TEXT,
            model_used      TEXT,
            news_count      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fund_code, trade_date, source)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_fund_date ON ai_analysis_cache(fund_code, trade_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_created ON ai_analysis_cache(created_at)")

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
