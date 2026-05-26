import os
import asyncio
import pandas as pd
from pathlib import Path
from app.services.data.akshare_client import fetch_data, get_index_daily

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

INDEX_MAP = {
    "hs300": "sh000300",
    "zz500": "sh000905",
    "zz1000": "sh000852",
    "cyb": "sz399006",
    "kcb50": "sh000688",
    "sz50": "sh000016",
}


def _ensure_raw_dir():
    d = PROJECT_ROOT / "data" / "raw" / "index"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


async def get_index_data(index_code: str, session, days=None):
    df = await fetch_data(get_index_daily, index_code)
    if df is not None and not df.empty:
        raw_dir = _ensure_raw_dir()
        df.to_csv(os.path.join(raw_dir, f"{index_code}.csv"), index=False, encoding="utf-8-sig")
    if days is not None and df is not None:
        return df.head(days)
    return df


async def fetch_all_indices(session):
    tasks = [get_index_data(symbol, session) for symbol in INDEX_MAP.values()]
    await asyncio.gather(*tasks, return_exceptions=True)