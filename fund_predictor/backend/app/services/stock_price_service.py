import logging
from datetime import datetime

import pandas as pd

from app.core.config import RAW_DIR
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)


def _get_exchange_prefix(stock_code: str) -> str:
    code = str(stock_code).zfill(6)
    if code.startswith(("600", "601", "603", "605", "688")):
        return "sh"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return "sz"
    if code.startswith(("8", "4")):
        return "bj"
    return "sz"


def _fetch_akshare_hist(stock_code: str) -> tuple[pd.DataFrame | None, str]:
    try:
        import akshare as ak

        raw = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20200101", end_date="20500101", adjust="qfq")
        if raw is None or raw.empty:
            return None, "empty_data"
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(raw["日期"], errors="coerce"),
                "open": pd.to_numeric(raw["开盘"], errors="coerce"),
                "high": pd.to_numeric(raw["最高"], errors="coerce"),
                "low": pd.to_numeric(raw["最低"], errors="coerce"),
                "close": pd.to_numeric(raw["收盘"], errors="coerce"),
                "volume": pd.to_numeric(raw["成交量"], errors="coerce"),
            }
        ).dropna(subset=["date", "close"]).sort_values("date")
        out["ret"] = out["close"].pct_change()
        out["source"] = "akshare_stock_zh_a_hist"
        return out, "akshare_stock_zh_a_hist"
    except Exception as exc:
        logger.warning("stock_daily_source_failed stock_code=%s source=akshare_stock_zh_a_hist error=%s", stock_code, exc)
        return None, f"akshare_hist_error: {exc}"


def _fetch_akshare_daily(stock_code: str) -> tuple[pd.DataFrame | None, str]:
    try:
        import akshare as ak

        prefix = _get_exchange_prefix(stock_code)
        symbol = f"{prefix}{stock_code}"
        raw = ak.stock_zh_a_daily(symbol=symbol, adjust="qfq")
        if raw is None or raw.empty:
            return None, "empty_data"
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(raw["date"], errors="coerce"),
                "open": pd.to_numeric(raw["open"], errors="coerce"),
                "high": pd.to_numeric(raw["high"], errors="coerce"),
                "low": pd.to_numeric(raw["low"], errors="coerce"),
                "close": pd.to_numeric(raw["close"], errors="coerce"),
                "volume": pd.to_numeric(raw["volume"], errors="coerce"),
            }
        ).dropna(subset=["date", "close"]).sort_values("date")
        out["ret"] = out["close"].pct_change()
        out["source"] = "akshare_stock_zh_a_daily"
        return out, "akshare_stock_zh_a_daily"
    except Exception as exc:
        logger.warning("stock_daily_source_failed stock_code=%s source=akshare_stock_zh_a_daily error=%s", stock_code, exc)
        return None, f"akshare_daily_error: {exc}"


def _fetch_eastmoney_stock(stock_code: str) -> tuple[pd.DataFrame | None, str]:
    try:
        import requests

        prefix = _get_exchange_prefix(stock_code)
        secid = f"{'1' if prefix == 'sh' else '0'}.{stock_code}"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "klt": "101",
            "fqt": "1",
            "beg": "20000101",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        klines = data.get("klines") or []
        if not klines:
            return None, "empty_data"
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
            }
        ).dropna(subset=["date", "close"]).sort_values("date")
        out["ret"] = out["close"].pct_change()
        out["source"] = "eastmoney_stock_kline"
        return out, "eastmoney_stock_kline"
    except Exception as exc:
        logger.warning("stock_daily_source_failed stock_code=%s source=eastmoney_stock_kline error=%s", stock_code, exc)
        return None, f"eastmoney_error: {exc}"


def get_stock_daily_multi_source(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> tuple[pd.DataFrame, dict]:
    set_log_context(stage="stock_daily_multi_source_start")
    logger.info("stock_daily_multi_source_start stock_code=%s", stock_code)

    code = str(stock_code).zfill(6)
    path = RAW_DIR / "stocks" / f"{code}.csv"

    if path.exists():
        try:
            cached = pd.read_csv(path, parse_dates=["date"])
            if not cached.empty and len(cached) >= 30:
                set_log_context(stage="stock_daily_source_success")
                logger.info("stock_daily_source_success stock_code=%s source=cache rows=%s", code, len(cached))
                return cached, {"source": "cache", "stock_code": code}
        except Exception as exc:
            logger.warning("stock_cache_read_failed stock_code=%s error=%s", code, exc)

    sources = [
        ("akshare_stock_zh_a_hist", lambda: _fetch_akshare_hist(code)),
        ("akshare_stock_zh_a_daily", lambda: _fetch_akshare_daily(code)),
        ("eastmoney_stock_kline", lambda: _fetch_eastmoney_stock(code)),
    ]

    errors = []
    for source_name, fetcher in sources:
        set_log_context(stage="stock_daily_source_try")
        logger.info("stock_daily_source_try stock_code=%s source=%s", code, source_name)
        df, result = fetcher()
        if df is not None and not df.empty:
            if start_date:
                df = df[df["date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["date"] <= pd.to_datetime(end_date)]
            if len(df) >= 10:
                path.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(path, index=False, encoding="utf-8")
                set_log_context(stage="stock_daily_source_success")
                logger.info("stock_daily_source_success stock_code=%s source=%s rows=%s", code, result, len(df))
                return df, {"source": result, "stock_code": code}
        errors.append(f"{source_name}: {result}")

    set_log_context(stage="stock_daily_all_sources_failed")
    logger.exception("stock_daily_all_sources_failed stock_code=%s errors=%s", code, errors)
    return pd.DataFrame(), {"source": "all_failed", "stock_code": code, "errors": errors}
