import json
import asyncio
from datetime import datetime, timedelta
from functools import partial
import httpx
import pandas as pd
from app.core.errors import DataFetchError


DJ_BASE = "https://danjuanfunds.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://danjuanfunds.com/",
}


async def _get(url: str, params: dict = None, timeout: int = 15) -> dict:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


async def search_funds(keyword: str, limit: int = 20) -> list[dict]:
    from .fund_cache_service import ensure_cache_exists, search_local
    
    # 1. 首先尝试本地缓存搜索
    try:
        if ensure_cache_exists():
            local_results = search_local(keyword, limit)
            if local_results:
                return local_results
    except Exception as e:
        pass
    
    # 2. 本地无匹配，回退到东方财富API
    try:
        em_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "https://fund.eastmoney.com/",
            "Accept": "*/*",
        }
        url = "http://fund.eastmoney.com/data/FundGuideapi.aspx"
        params = {
            "dt": 0,
            "ft": "",
            "sd": "",
            "ed": "",
            "sc": "1yzf",
            "st": "desc",
            "pi": 1,
            "pn": min(limit, 50),
            "zf": "diy",
            "sh": "list",
            "keyword": keyword,
        }
        async with httpx.AsyncClient(headers=em_headers, follow_redirects=True) as client:
            resp = await client.get(url, params=params, timeout=10)
            if resp.status_code == 200 and resp.text.strip().startswith("var rankData"):
                text = resp.text
                json_str = text.replace("var rankData=", "").rstrip(";")
                data = json.loads(json_str)
                items = data.get("datas", [])
                results = []
                for item in items[:limit]:
                    parts = item.split(",")
                    if len(parts) >= 3:
                        code = parts[0].strip()
                        name = parts[1].strip()
                        fund_type_raw = parts[2].strip() if len(parts) > 2 else ""
                        if code and name:
                            results.append({
                                "fund_code": code,
                                "fund_name": name,
                                "fund_type_raw": fund_type_raw,
                                "company": "",
                            })
                return results
    except Exception as e:
        pass

    # 3. 如果是数字代码，尝试直接获取基金信息
    if keyword.isdigit() and len(keyword) >= 4:
        try:
            info = await get_fund_info(keyword.zfill(6))
            if info.get("fund_name"):
                return [{
                    "fund_code": info["fund_code"],
                    "fund_name": info["fund_name"],
                    "fund_type_raw": "",
                    "company": info.get("keeper_name", ""),
                }]
        except Exception:
            pass

    return []


async def get_fund_info(fund_code: str) -> dict:
    url = f"{DJ_BASE}/djapi/fund/{fund_code}"
    data = await _get(url)
    if data.get("result_code") not in (0, None):
        raise DataFetchError(f"蛋卷基金API错误: {data.get('message', 'unknown')}")
    fd = data.get("data", {})
    derived = fd.get("fund_derived", {})
    op = fd.get("op_fund", {})
    return {
        "fund_code": fd.get("fd_code", fund_code),
        "fund_name": fd.get("fd_name", ""),
        "full_name": fd.get("fd_full_name", ""),
        "found_date": fd.get("found_date", ""),
        "keeper_name": fd.get("keeper_name", ""),
        "manager_name": fd.get("manager_name", ""),
        "totshare": fd.get("totshare", ""),
        "trup_name": fd.get("trup_name", ""),
        "type_desc": fd.get("type_desc", ""),
        "rating_desc": fd.get("rating_desc", ""),
        "risk_level": fd.get("risk_level"),
        "style_tips": op.get("tips", "") if isinstance(op, dict) else "",
        "unit_nav": derived.get("unit_nav"),
        "nav_grtd": derived.get("nav_grtd"),
        "nav_grl1m": derived.get("nav_grl1m"),
        "nav_grl3m": derived.get("nav_grl3m"),
        "nav_grlty": derived.get("nav_grlty"),
        "nav_grl1y": derived.get("nav_grl1y"),
        "nav_grl6m": derived.get("nav_grl6m"),
        "nav_grl3y": derived.get("nav_grl3y"),
        "nav_grl5y": derived.get("nav_grl5y"),
        "annual_performance": derived.get("annual_performance_list", []),
        "benchmark_index": fd.get("benchmark_index", []),
        "performance_bench_mark": fd.get("performance_bench_mark", ""),
        "invest_orientation": fd.get("invest_orientation", ""),
        "invest_target": fd.get("invest_target", ""),
        "follower_count": fd.get("follower_count"),
    }


async def get_fund_detail(fund_code: str) -> dict:
    url = f"{DJ_BASE}/djapi/fund/detail/{fund_code}"
    data = await _get(url)
    detail = data.get("data", {})
    holdings = detail.get("stock_list", [])
    bonds = detail.get("bond_list", [])
    industry = detail.get("industry_list", [])
    fee = detail.get("fee_to", {})
    manager_info = detail.get("manager_info", {})
    return {
        "fund_code": fund_code,
        "holdings": [{"name": h.get("name"), "code": h.get("code"), "percent": h.get("percent")} for h in holdings],
        "bonds": [{"name": b.get("name"), "percent": b.get("percent")} for b in bonds],
        "industry_allocation": [{"name": i.get("name"), "percent": i.get("percent")} for i in industry],
        "fee_rate": fee,
        "manager_info": manager_info,
    }


async def get_asset_percent(fund_code: str, report_date: str = "") -> dict:
    params = {"fund_code": fund_code}
    if report_date:
        params["report_date"] = report_date
    url = f"{DJ_BASE}/djapi/fundx/base/fund/record/asset/percent"
    asset_headers = {
        **HEADERS,
        "Referer": f"{DJ_BASE}/funding/{fund_code}",
    }
    async with httpx.AsyncClient(headers=asset_headers, follow_redirects=True) as client:
        resp = await client.get(url, params=params, timeout=15)
        if resp.status_code == 403:
            return await _fallback_asset_from_detail(fund_code)
        resp.raise_for_status()
        data = resp.json()
    items = data.get("data", {}).get("item_list", []) or []
    result = []
    for item in items:
        result.append({
            "name": item.get("name", ""),
            "code": (item.get("code") or "").strip().zfill(6),
            "percent": item.get("percent"),
            "type_code": item.get("type_code", ""),
            "report_date": report_date or item.get("report_date", ""),
        })
    return {
        "fund_code": fund_code,
        "items": result,
        "report_date": report_date or "",
    }


async def _fallback_asset_from_detail(fund_code: str) -> dict:
    try:
        detail = await get_fund_detail(fund_code)
        stocks = detail.get("holdings", [])
        bonds = detail.get("bonds", [])
        items = []
        for s in stocks:
            items.append({
                "name": s.get("name", ""),
                "code": (s.get("code") or "").strip().zfill(6),
                "percent": s.get("percent"),
                "type_code": "stock",
            })
        for b in bonds:
            items.append({
                "name": b.get("name", ""),
                "code": "",
                "percent": b.get("percent"),
                "type_code": "bond",
            })
        return {"fund_code": fund_code, "items": items, "report_date": "", "source": "detail_fallback"}
    except Exception:
        return {"fund_code": fund_code, "items": [], "report_date": ""}


async def get_fund_growth(fund_code: str, period: str = "3y") -> list[dict]:
    url = f"{DJ_BASE}/djapi/fund/growth/{fund_code}"
    data = await _get(url, params={"day": period})
    growth_data = data.get("data", {}).get("fund_nav_growth", [])
    return growth_data


async def get_fund_nav_history(fund_code: str, days: int = 800) -> pd.DataFrame:
    growth_data = await get_fund_growth(fund_code, period="3y")
    if not growth_data:
        raise DataFetchError(f"基金 {fund_code} 无净值历史数据")
    rows = []
    for item in growth_data:
        nav_str = item.get("nav")
        date_str = item.get("date")
        pct_str = item.get("percentage")
        if nav_str and date_str:
            try:
                nav_val = float(nav_str)
                daily_return = float(pct_str) / 100.0 if pct_str else None
                rows.append({
                    "nav_date": date_str,
                    "nav": nav_val,
                    "daily_return": daily_return,
                    "pct_change": float(pct_str) if pct_str else None,
                })
            except (ValueError, TypeError):
                continue
    if not rows:
        raise DataFetchError(f"基金 {fund_code} 净值数据解析失败")
    df = pd.DataFrame(rows)
    df["nav_date"] = pd.to_datetime(df["nav_date"])
    df = df.sort_values("nav_date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["nav_date"], keep="last")
    if len(df) < days:
        pass
    return df.tail(days)


async def get_realtime_quote_xueqiu(symbol: str = "SH000001") -> dict:
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": "https://xueqiu.com/",
        "Accept": "application/json",
    }
    url = f"https://stock.xueqiu.com/v5/stock/quote.json"
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        resp = await client.get(url, params={"symbol": symbol, "extend": "detail"}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        quote = data.get("data", {}).get("quote", {})
        market = data.get("data", {}).get("market", {})
        return {
            "symbol": quote.get("symbol", symbol),
            "name": quote.get("name", ""),
            "current": quote.get("current"),
            "percent": quote.get("percent"),
            "chg": quote.get("chg"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "last_close": quote.get("last_close"),
            "volume": quote.get("volume"),
            "amount": quote.get("amount"),
            "timestamp": quote.get("timestamp"),
            "status": market.get("status", ""),
            "market_status_id": market.get("status_id"),
        }


async def batch_quotes_xueqiu(symbols: list[str]) -> dict[str, dict]:
    symbol_str = ",".join(symbols)
    result = {}
    for sym in symbols:
        try:
            q = await get_realtime_quote_xueqiu(sym)
            result[sym] = q
        except Exception:
            result[sym] = None
    return result