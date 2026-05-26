import os
import pandas as pd
from cachetools import TTLCache
from threading import RLock
from pathlib import Path
from sqlalchemy import select, desc
from app.models.fund_nav import FundNav
from app.services.data.akshare_client import fetch_data, get_fund_nav_em, get_fund_nav_xq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_nav_cache = TTLCache(maxsize=500, ttl=86400)
_nav_lock = RLock()


def _get_cached(fund_code: str):
    with _nav_lock:
        return _nav_cache.get(fund_code)


def _set_cached(fund_code: str, df: pd.DataFrame):
    with _nav_lock:
        _nav_cache[fund_code] = df


def _ensure_raw_dir():
    d = PROJECT_ROOT / "data" / "raw" / "fund_nav"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


async def fetch_and_store_nav(fund_code: str, session):
    df = None
    try:
        from app.services.data.danjuan_client import get_fund_nav_history as dj_nav_history
        df = await dj_nav_history(fund_code)
        df["source"] = "danjuan"
    except Exception as e:
        pass

    if (df is None or df.empty):
        try:
            df = await fetch_data(get_fund_nav_em, fund_code)
            if df is not None and not df.empty:
                df["source"] = "em"
        except Exception:
            pass

    if (df is None or df.empty):
        try:
            df = await fetch_data(get_fund_nav_xq, fund_code)
            if df is not None and not df.empty:
                df["source"] = "xq"
        except Exception:
            pass

    if df is None or df.empty:
        raise ValueError(f"基金 {fund_code} 净值数据为空")

    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "净值日期" in c or "date" in cl:
            col_map[c] = "nav_date"
        elif "单位净值" in c or "nav" in cl:
            col_map[c] = "nav"
        elif "日增长率" in c or "daily" in cl or "return" in cl or "percentage" in cl:
            col_map[c] = "daily_return"
        elif "累计净值" in c or "acc" in cl:
            col_map[c] = "acc_nav"
    df = df.rename(columns=col_map)
    if "nav_date" not in df.columns:
        df["nav_date"] = df.index.astype(str)
    df["fund_code"] = fund_code
    raw_dir = _ensure_raw_dir()
    csv_path = os.path.join(raw_dir, f"{fund_code}.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    for _, row in df.iterrows():
        nav_date_str = str(row["nav_date"])
        result = await session.execute(
            select(FundNav).where(
                FundNav.fund_code == fund_code,
                FundNav.nav_date == nav_date_str
            )
        )
        existing = result.scalar_one_or_none()
        source = row.get("source", "em") if "source" in row else "em"
        if existing:
            existing.nav = float(row["nav"]) if pd.notna(row.get("nav")) else existing.nav
            if "daily_return" in row and pd.notna(row.get("daily_return")):
                existing.daily_return = float(row["daily_return"])
            if "acc_nav" in row and pd.notna(row.get("acc_nav")):
                existing.acc_nav = float(row["acc_nav"])
        else:
            session.add(FundNav(
                fund_code=fund_code,
                nav_date=nav_date_str,
                nav=float(row["nav"]) if pd.notna(row.get("nav")) else 0,
                daily_return=float(row["daily_return"]) if pd.notna(row.get("daily_return")) else None,
                acc_nav=float(row["acc_nav"]) if pd.notna(row.get("acc_nav")) else None,
                source=source,
            ))
    await session.commit()
    _set_cached(fund_code, df)
    return df


async def get_nav_data(fund_code: str, session, days=None):
    cached = _get_cached(fund_code)
    if cached is not None:
        df = cached
    else:
        result = await session.execute(
            select(FundNav)
            .where(FundNav.fund_code == fund_code)
            .order_by(desc(FundNav.nav_date))
        )
        records = result.scalars().all()
        if records:
            data = [
                {
                    "nav_date": r.nav_date,
                    "nav": r.nav,
                    "acc_nav": r.acc_nav,
                    "daily_return": r.daily_return,
                    "adj_nav": r.adj_nav,
                }
                for r in records
            ]
            _set_cached(fund_code, pd.DataFrame(data))
            df = pd.DataFrame(data)
        else:
            df = await fetch_and_store_nav(fund_code, session)
            data = df.to_dict("records")
            if days:
                return data[:days]
            return data
    data = df.to_dict("records")
    if days:
        return data[:days]
    return data