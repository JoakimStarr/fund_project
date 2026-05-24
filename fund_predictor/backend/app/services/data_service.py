import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from app.core.config import (
    FETCH_MAX_WORKERS,
    FETCH_TIMEOUT,
    INDEX_SYMBOLS,
    MIN_TRAIN_ROWS,
    RAW_DIR,
    STALE_DAYS,
)
from app.core.errors import AppError, DataFetchError, DataStaleError
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)


def _is_stale(df: pd.DataFrame) -> bool:
    if df.empty:
        return True
    latest = pd.to_datetime(df["date"]).max().date()
    return (datetime.now().date() - latest).days > STALE_DAYS


def _read_cache(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path, parse_dates=["date"])
    return None


def _nav_meta(df: pd.DataFrame, source: str, fallback_used: bool = False, fallback_reason: str | None = None) -> dict:
    return {
        "source_used": source,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "stale": _is_stale(df),
        "nav_rows": int(len(df)),
        "nav_start_date": str(pd.to_datetime(df["date"]).min().date()) if len(df) else None,
        "nav_end_date": str(pd.to_datetime(df["date"]).max().date()) if len(df) else None,
        "nav_source": source,
    }


def _normalize_fund_nav(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise DataFetchError("Fund NAV source returned empty data", details={"source": source})

    columns = {str(c).strip(): c for c in df.columns}

    def pick(*names: str):
        for name in names:
            if name in columns:
                return columns[name]
        return None

    date_col = pick("净值日期", "date", "日期")
    nav_col = pick("单位净值", "nav", "单位净值走势")
    acc_col = pick("累计净值", "acc_nav")
    growth_col = pick("日增长率", "daily_growth_pct", "涨跌幅")
    if date_col is None or nav_col is None:
        raise DataFetchError(
            "Fund NAV source missing required columns",
            details={"source": source, "columns": [str(c) for c in df.columns]},
        )

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
            "source": source,
        }
    )
    if acc_col is not None:
        out["acc_nav"] = pd.to_numeric(df[acc_col], errors="coerce")
    else:
        out["acc_nav"] = out["nav"]
    if growth_col is not None:
        growth = df[growth_col].astype(str).str.replace("%", "", regex=False)
        out["daily_growth_pct"] = pd.to_numeric(growth, errors="coerce")
    else:
        out["daily_growth_pct"] = out["nav"].pct_change() * 100

    return out.dropna(subset=["date", "nav"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)


def _fetch_fund_nav_akshare(fund_code: str) -> pd.DataFrame:
    try:
        import akshare as ak
    except Exception as exc:
        raise DataFetchError("AkShare is not installed or cannot be imported", details={"reason": str(exc)}) from exc

    unit = ak.fund_open_fund_info_em(symbol=fund_code, indicator="\u5355\u4f4d\u51c0\u503c\u8d70\u52bf")
    acc = ak.fund_open_fund_info_em(symbol=fund_code, indicator="\u7d2f\u8ba1\u51c0\u503c\u8d70\u52bf")
    unit_df = _normalize_fund_nav(unit, "akshare_fund_open_fund_info_em")
    if acc is not None and not acc.empty:
        acc_cols = {str(c).strip(): c for c in acc.columns}
        if "净值日期" in acc_cols and "累计净值" in acc_cols:
            acc_df = pd.DataFrame(
                {
                    "date": pd.to_datetime(acc[acc_cols["净值日期"]], errors="coerce"),
                    "acc_nav": pd.to_numeric(acc[acc_cols["累计净值"]], errors="coerce"),
                }
            ).dropna(subset=["date"])
            unit_df = unit_df.drop(columns=["acc_nav"], errors="ignore").merge(acc_df, on="date", how="left")
            unit_df["acc_nav"] = unit_df["acc_nav"].fillna(unit_df["nav"])
    return unit_df


def _fetch_fund_nav_eastmoney_html(fund_code: str) -> pd.DataFrame:
    url = "https://fundf10.eastmoney.com/F10DataApi.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{fund_code}.html",
    }
    rows = []
    pages = 1
    for page in range(1, 400):
        params = {"type": "lsjz", "code": fund_code, "page": page, "per": 20, "sdate": "", "edate": ""}
        resp = requests.get(url, params=params, headers=headers, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        if page == 1:
            match = re.search(r"pages:(\d+)", text)
            pages = int(match.group(1)) if match else 1
        tables = pd.read_html(StringIO(text))
        if not tables or tables[0].empty:
            break
        rows.append(tables[0])
        if page >= pages:
            break
    if not rows:
        raise DataFetchError("Eastmoney HTML NAV source returned empty data", details={"fund_code": fund_code})
    return _normalize_fund_nav(pd.concat(rows, ignore_index=True), "eastmoney_html")


def get_fund_nav(fund_code: str, require_fresh: bool = False) -> tuple[pd.DataFrame, dict]:
    set_log_context(fund_code=fund_code, stage="data_fetch_start")
    logger.info("data_fetch_start fund nav")
    path = RAW_DIR / "fund_nav" / f"{fund_code}.csv"
    cached = _read_cache(path)
    if cached is not None and not require_fresh and not _is_stale(cached) and len(cached) >= MIN_TRAIN_ROWS + 1:
        return cached, _nav_meta(cached, "cache", fallback_used=False)

    primary_error: Exception | None = None
    try:
        out = _fetch_fund_nav_akshare(fund_code)
        if require_fresh and _is_stale(out):
            raise DataStaleError("Fund NAV latest date is stale", details={"fund_code": fund_code, "latest": str(out["date"].max().date())})
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False, encoding="utf-8")
        meta = _nav_meta(out, "akshare_fund_open_fund_info_em", fallback_used=False)
        set_log_context(stage="data_fetch_success")
        logger.info("data_fetch_success fund nav fund_code=%s rows=%s start=%s end=%s source=%s", fund_code, meta["nav_rows"], meta["nav_start_date"], meta["nav_end_date"], meta["source_used"])
        return out, meta
    except AppError as exc:
        primary_error = exc
        logger.exception("data_fetch_failed fund nav primary")
    except Exception as exc:
        primary_error = exc
        logger.exception("data_fetch_failed fund nav primary")

    try:
        out = _fetch_fund_nav_eastmoney_html(fund_code)
        if require_fresh and _is_stale(out):
            raise DataStaleError("Fallback fund NAV latest date is stale", details={"fund_code": fund_code, "latest": str(out["date"].max().date())})
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False, encoding="utf-8")
        meta = _nav_meta(out, "eastmoney_html", fallback_used=True, fallback_reason=str(primary_error))
        set_log_context(stage="data_fetch_success")
        logger.info("data_fetch_success fund nav fallback fund_code=%s rows=%s start=%s end=%s source=%s", fund_code, meta["nav_rows"], meta["nav_start_date"], meta["nav_end_date"], meta["source_used"])
        return out, meta
    except AppError:
        raise
    except Exception as fallback_exc:
        set_log_context(stage="data_fetch_failed")
        logger.exception("data_fetch_failed fund nav fallback")
        if cached is not None and not require_fresh:
            meta = _nav_meta(cached, "cache", fallback_used=True, fallback_reason=str(fallback_exc))
            return cached, meta
        raise DataFetchError(
            "Fund NAV fetch failed",
            details={"reason": str(fallback_exc), "primary_reason": str(primary_error), "fund_code": fund_code},
        ) from fallback_exc


def _secid(symbol: str) -> str:
    if symbol.startswith("sh"):
        return "1." + symbol[2:]
    if symbol.startswith("sz"):
        return "0." + symbol[2:]
    raise DataFetchError("Unsupported index symbol format", details={"symbol": symbol})


def _fetch_index_sohu(symbol: str) -> pd.DataFrame:
    code = symbol[2:]
    url = "https://q.stock.sohu.com/hisHq"
    params = {
        "code": f"zs_{code}",
        "start": "20000101",
        "end": "20500101",
        "stat": "1",
        "order": "D",
        "period": "d",
        "callback": "historySearchHandler",
        "rt": "jsonp",
    }
    resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    match = re.search(r"historySearchHandler\((.*)\)$", resp.text)
    if not match:
        raise DataFetchError("Sohu index response format is invalid", details={"symbol": symbol})
    payload = json.loads(match.group(1))
    hq = payload[0].get("hq", []) if payload else []
    if not hq:
        raise DataFetchError("Sohu index source returned empty data", details={"symbol": symbol})
    df = pd.DataFrame(hq, columns=["date", "open", "close", "change", "pct", "low", "high", "volume", "amount", "unknown"])
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"]),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
            "source": "sohu",
        }
    )
    return out.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")


def get_index_daily(symbol: str, require_fresh: bool = False) -> tuple[pd.DataFrame, dict]:
    path = RAW_DIR / "index" / f"{symbol}.csv"
    cached = _read_cache(path)
    if cached is not None and not require_fresh and not _is_stale(cached):
        return cached, {"source_used": "cache", "fallback_used": False, "stale": False}
    try:
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": _secid(symbol),
            "klt": "101",
            "fqt": "1",
            "beg": "20000101",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        klines = data.get("klines") or []
        if not klines:
            raise DataFetchError("Eastmoney index source returned empty data", details={"symbol": symbol})
        parsed = [line.split(",") for line in klines]
        df = pd.DataFrame(parsed, columns=["date", "open", "close", "high", "low", "volume", "amount"])
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["date"]),
                "open": pd.to_numeric(df["open"], errors="coerce"),
                "high": pd.to_numeric(df["high"], errors="coerce"),
                "low": pd.to_numeric(df["low"], errors="coerce"),
                "close": pd.to_numeric(df["close"], errors="coerce"),
                "volume": pd.to_numeric(df["volume"], errors="coerce"),
                "source": "eastmoney",
            }
        ).dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
        if require_fresh and _is_stale(out):
            raise DataStaleError("Index latest date is stale", details={"symbol": symbol, "latest": str(out["date"].max().date())})
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False, encoding="utf-8")
        return out, {"source_used": "eastmoney", "fallback_used": False, "stale": _is_stale(out)}
    except AppError:
        raise
    except Exception as exc:
        logger.exception("data_fetch_failed index")
        try:
            out = _fetch_index_sohu(symbol)
            if require_fresh and _is_stale(out):
                raise DataStaleError("Fallback index latest date is stale", details={"symbol": symbol, "latest": str(out["date"].max().date())})
            path.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(path, index=False, encoding="utf-8")
            return out, {"source_used": "sohu", "fallback_used": True, "fallback_reason": str(exc), "stale": _is_stale(out)}
        except AppError:
            raise
        except Exception as fallback_exc:
            logger.exception("data_fetch_failed index fallback")
            if cached is not None and not require_fresh:
                return cached, {"source_used": "cache", "fallback_used": True, "fallback_reason": str(fallback_exc), "stale": _is_stale(cached)}
            raise DataFetchError("Index fetch failed", details={"reason": str(fallback_exc), "symbol": symbol}) from fallback_exc


def _fetch_single_index(args: tuple[str, str, bool]) -> tuple[str, tuple[pd.DataFrame, dict]]:
    name, symbol, fresh = args
    result = get_index_daily(symbol, require_fresh=fresh)
    return name, result


def load_market_data(require_fresh: bool = False) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """并发获取所有指数数据，使用ThreadPoolExecutor加速"""
    tasks = [(name, sym, require_fresh) for name, sym in INDEX_SYMBOLS.items()]
    
    frames = {}
    meta = []
    
    with ThreadPoolExecutor(max_workers=FETCH_MAX_WORKERS, thread_name_prefix="idx_fetch") as executor:
        future_to_name = {executor.submit(_fetch_single_index, task): task[0] for task in tasks}
        
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                idx_name, (df, info) = future.result()
                frames[idx_name] = df
                meta.append({"name": idx_name, "symbol": INDEX_SYMBOLS.get(idx_name, ""), **info})
            except Exception as exc:
                logger.error("index_fetch_concurrent_failed name=%s error=%s", name, exc)
                meta.append({"name": name, "error": str(exc)})
    
    return frames, meta