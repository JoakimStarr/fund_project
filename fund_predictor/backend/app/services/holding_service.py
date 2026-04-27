import logging
import re
from datetime import datetime

import pandas as pd

from app.core.config import RAW_DIR
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)


def _quarter_report_date(text: str) -> str:
    text = str(text)
    year_match = re.search(r"(\d{4})", text)
    year = year_match.group(1) if year_match else str(datetime.now().year)
    if "1季度" in text:
        return f"{year}-03-31"
    if "2季度" in text or "半年" in text:
        return f"{year}-06-30"
    if "3季度" in text:
        return f"{year}-09-30"
    return f"{year}-12-31"


def get_fund_holdings(fund_code: str) -> tuple[pd.DataFrame, dict]:
    set_log_context(fund_code=fund_code, stage="holding_fetch_start")
    logger.info("holding_fetch_start")
    path = RAW_DIR / "holdings" / f"{fund_code}.csv"
    try:
        if path.exists():
            df = pd.read_csv(path, dtype={"stock_code": str})
            if not df.empty:
                return df, {
                    "holding_available": True,
                    "holding_scope": df.get("holding_scope", pd.Series(["top10"])).iloc[0],
                    "holding_report_date": str(df["report_date"].max()),
                    "source": "cache",
                }

        import akshare as ak

        frames = []
        current_year = datetime.now().year
        for year in range(current_year, current_year - 4, -1):
            try:
                raw = ak.fund_portfolio_hold_em(symbol=fund_code, date=str(year))
                if raw is not None and not raw.empty:
                    frames.append(raw)
            except Exception:
                logger.exception("holding_fetch_year_failed year=%s", year)
        if not frames:
            raise RuntimeError("No holding rows returned from akshare fund_portfolio_hold_em")

        raw = pd.concat(frames, ignore_index=True)
        required = {"序号", "股票代码", "股票名称", "占净值比例", "持股数", "持仓市值", "季度"}
        missing = required - set(raw.columns)
        if missing:
            raise RuntimeError(f"Holding columns missing: {sorted(missing)}")
        raw["report_date"] = raw["季度"].map(_quarter_report_date)
        latest_report = raw["report_date"].max()
        latest = raw[raw["report_date"] == latest_report].copy()
        latest = latest.sort_values("序号").head(10)
        out = pd.DataFrame(
            {
                "fund_code": fund_code,
                "report_date": latest["report_date"],
                "stock_code": latest["股票代码"].astype(str).str.zfill(6),
                "stock_name": latest["股票名称"].astype(str),
                "shares": pd.to_numeric(latest["持股数"], errors="coerce"),
                "market_value": pd.to_numeric(latest["持仓市值"], errors="coerce"),
                "weight_nav": pd.to_numeric(latest["占净值比例"], errors="coerce") / 100.0,
                "rank": pd.to_numeric(latest["序号"], errors="coerce"),
                "source": "akshare_fund_portfolio_hold_em",
                "holding_scope": "top10",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        ).dropna(subset=["stock_code", "weight_nav"])
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False, encoding="utf-8")
        set_log_context(stage="holding_fetch_success")
        logger.info("holding_fetch_success rows=%s report_date=%s", len(out), latest_report)
        return out, {
            "holding_available": not out.empty,
            "holding_scope": "top10" if not out.empty else "unavailable",
            "holding_report_date": latest_report if not out.empty else None,
            "source": "akshare_fund_portfolio_hold_em",
        }
    except Exception as exc:
        set_log_context(stage="holding_fetch_failed")
        logger.exception("holding_fetch_failed")
        return pd.DataFrame(), {
            "holding_available": False,
            "holding_scope": "unavailable",
            "holding_report_date": None,
            "source": "akshare_fund_portfolio_hold_em",
            "reason": str(exc),
            "fund_code": fund_code,
        }


def get_stock_daily(stock_code: str) -> tuple[pd.DataFrame, dict]:
    from app.services.stock_price_service import get_stock_daily_multi_source

    return get_stock_daily_multi_source(stock_code)
