import asyncio
import logging
import pandas as pd
from app.services.data.akshare_client import fetch_data, get_bond_yield, get_shibor, get_exchange_rate, get_north_flow

logger = logging.getLogger(__name__)


async def get_bond_data(session, days=None):
    df = await fetch_data(get_bond_yield, "20240101")
    if days is not None and df is not None:
        return df.head(days)
    return df


async def get_shibor_data(session, days=None):
    df = await fetch_data(get_shibor)
    if days is not None and df is not None:
        return df.head(days)
    return df


async def fetch_all_macro(session):
    tasks = [
        get_bond_data(session),
        get_shibor_data(session),
        fetch_data(get_exchange_rate, "USD"),
        fetch_data(get_north_flow),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for name, res in zip(["bond", "shibor", "exchange", "north"], results):
        if isinstance(res, Exception):
            logger.error(f"宏观数据 {name} 获取失败: {res}")