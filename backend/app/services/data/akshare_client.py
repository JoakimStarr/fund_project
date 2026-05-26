import asyncio
import pandas as pd
import akshare as ak
from functools import partial
from app.core.errors import DataFetchError


async def fetch_data(func, *args, max_retries=2, timeout=20, **kwargs):
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            loop = asyncio.get_running_loop()
            fn = partial(func, *args, **kwargs)
            result = await asyncio.wait_for(
                loop.run_in_executor(None, fn),
                timeout=timeout
            )
            if result is None or (isinstance(result, pd.DataFrame) and result.empty):
                raise ValueError("empty result")
            return result
        except asyncio.TimeoutError:
            last_error = TimeoutError(f"fetch timeout after {timeout}s")
        except Exception as e:
            last_error = e
    raise DataFetchError(f"数据获取失败: {last_error}")


def get_fund_nav_em(fund_code: str) -> pd.DataFrame:
    return ak.fund_open_fund_info_em(fund=fund_code, indicator="单位净值走势")


def get_fund_nav_xq(fund_code: str) -> pd.DataFrame:
    return ak.fund_open_fund_info_xq(symbol=fund_code, indicator="单位净值走势")


def get_fund_basic_info_xq(fund_code: str) -> pd.DataFrame:
    return ak.fund_individual_basic_info_xq(symbol=fund_code)


def get_fund_holdings(symbol: str, date: str = "2024") -> pd.DataFrame:
    return ak.fund_portfolio_hold_em(symbol=symbol, date=date)


def get_index_daily(symbol: str) -> pd.DataFrame:
    return ak.stock_zh_index_daily(symbol=symbol)


def get_bond_yield(start_date: str) -> pd.DataFrame:
    return ak.bond_zh_us_rate(start_date=start_date)


def get_shibor() -> pd.DataFrame:
    return ak.macro_china_shibor_all()


def get_exchange_rate(currency: str = "USD") -> pd.DataFrame:
    return ak.currency_boc_sina(currency=currency)


def get_north_flow() -> pd.DataFrame:
    return ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")


def get_cls_news() -> pd.DataFrame:
    return ak.stock_telegraph_cls_em()


def get_stock_news(symbol: str) -> pd.DataFrame:
    return ak.stock_news_em(symbol=symbol)