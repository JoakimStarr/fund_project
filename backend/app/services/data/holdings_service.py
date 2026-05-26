import os
import pandas as pd
from pathlib import Path
from app.services.data.akshare_client import fetch_data, get_fund_holdings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _ensure_raw_dir():
    d = PROJECT_ROOT / "data" / "raw" / "holdings"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


async def get_holdings(fund_code: str, session):
    df = await fetch_data(get_fund_holdings, fund_code)
    if df is not None and not df.empty:
        raw_dir = _ensure_raw_dir()
        df.to_csv(os.path.join(raw_dir, f"{fund_code}.csv"), index=False, encoding="utf-8-sig")
    return df


async def get_latest_holdings(fund_code: str, session):
    return await get_holdings(fund_code, session)