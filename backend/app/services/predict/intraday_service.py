from datetime import datetime
from sqlalchemy import select
import httpx
from app.core.config import settings
from app.models.fund_nav import FundNav
from app.models.fund_profile import FundProfileCache
from app.schemas.intraday import IntradayResponse, HoldingContribution, MarketSession
from app.schemas.predict import ConfidenceInterval
from app.services.fund.profile_service import get_fund_profile


def _get_market_session() -> MarketSession:
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    if weekday >= 5:
        return MarketSession(is_trading=False, session="closed", note="非交易日")
    if (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute <= 30):
        return MarketSession(is_trading=True, session="morning", note="上午交易时段")
    if (hour == 11 and minute > 30) or (hour == 12) or (hour == 13 and minute < 0):
        return MarketSession(is_trading=False, session="lunch_break", note="午间休市")
    if hour >= 13 and (hour < 15 or (hour == 15 and minute == 0)):
        return MarketSession(is_trading=True, session="afternoon", note="下午交易时段")
    return MarketSession(is_trading=False, session="closed", note="闭市")


async def estimate(fund_code: str, session, mode: str = "auto") -> IntradayResponse:
    profile = await get_fund_profile(fund_code)
    fund_name = profile.get("fund_name", "")
    fund_type = profile.get("fund_type", "hybrid_equity")
    nav_result = await session.execute(
        select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date.desc()).limit(1)
    )
    latest_nav_row = nav_result.scalar_one_or_none()
    if latest_nav_row is None:
        raise ValueError(f"基金 {fund_code} 无净值数据")
    prev_nav_val = float(latest_nav_row.nav)
    market_session = _get_market_session()
    if mode in ("holdings", "auto"):
        try:
            holdings_df = await _get_holdings(fund_code, session)
            if holdings_df is not None and len(holdings_df) > 0:
                return await _estimate_by_holdings(fund_code, fund_name, prev_nav_val, holdings_df, fund_type, market_session)
        except Exception:
            if mode == "holdings":
                raise ValueError("持仓数据获取失败")
    return await _estimate_by_index(fund_code, fund_name, prev_nav_val, fund_type, market_session)


async def _get_holdings(fund_code: str, session):
    from app.models.holdings import FundHolding
    result = await session.execute(
        select(FundHolding).where(FundHolding.fund_code == fund_code).order_by(FundHolding.rank).limit(10)
    )
    return result.scalars().all()


async def _estimate_by_holdings(fund_code: str, fund_name: str, prev_nav: float, holdings_list, fund_type: str, market_session: MarketSession) -> IntradayResponse:
    stock_codes = []
    holdings_used = []
    for h in holdings_list:
        code = str(h.stock_code).strip().zfill(6)
        weight = float(h.weight) / 100.0 if hasattr(h, "weight") and h.weight else 0.0
        name = h.stock_name or code
        if weight > 0:
            stock_codes.append(code)
            holdings_used.append(HoldingContribution(rank=len(holdings_used) + 1, code=code, name=name, weight=weight, price=None, prev_close=None, pct_change=0.0, contribution=0.0))
    if stock_codes:
        realtime_prices = await _fetch_sina_realtime(stock_codes)
        total_return = 0.0
        total_weight = 0.0
        for h in holdings_used:
            rt = realtime_prices.get(h.code, {})
            pct = float(rt.get("pct_change", 0))
            h.price = rt.get("price")
            h.prev_close = rt.get("prev_close")
            h.pct_change = pct
            h.contribution = round(h.weight * pct, 6)
            total_return += h.contribution
            total_weight += h.weight
        estimated_return = total_return / total_weight if total_weight > 0 else 0.0
    else:
        estimated_return = 0.0
    estimated_nav = prev_nav * (1 + estimated_return)
    estimated_return_pct = estimated_return * 100
    confidence = "high" if len(holdings_used) >= 5 else "medium"
    return IntradayResponse(fund_code=fund_code, fund_name=fund_name, estimated_nav=round(estimated_nav, 6), prev_nav=prev_nav, estimated_return=round(estimated_return, 6), estimated_return_pct=round(estimated_return_pct, 4), confidence=confidence, method="holdings_weighted", method_display="持仓加权法", market_session=market_session, holdings_used=holdings_used if holdings_used else None, timestamp=datetime.now().isoformat())


async def _estimate_by_index(fund_code: str, fund_name: str, prev_nav: float, fund_type: str, market_session: MarketSession) -> IntradayResponse:
    estimated_return = 0.0
    estimated_nav = prev_nav
    confidence = "low"
    return IntradayResponse(fund_code=fund_code, fund_name=fund_name, estimated_nav=round(estimated_nav, 6), prev_nav=prev_nav, estimated_return=0.0, estimated_return_pct=0.0, confidence=confidence, method="index_regression", method_display="指数回归法", market_session=market_session, timestamp=datetime.now().isoformat())


async def _fetch_sina_realtime(codes: list) -> dict:
    result = {}
    if not codes:
        return result
    codes_str = ",".join([f"sh{code}" if code.startswith("6") else f"sz{code}" for code in codes])
    url = f"https://hq.sinajs.cn/list={codes_str}"
    headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers=headers)
            text = resp.text
            for line in text.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    parts = line.split("=")
                    if len(parts) < 2:
                        continue
                    key = parts[0].strip().split("_")[-1]
                    data = parts[1].strip().strip('"').split(",")
                    if len(data) >= 4:
                        name = data[0]
                        price = float(data[3]) if data[3] else 0.0
                        prev_close = float(data[2]) if data[2] else 0.0
                        pct_change = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        result[key] = {"name": name, "price": price, "prev_close": prev_close, "pct_change": round(pct_change, 4)}
                except (IndexError, ValueError):
                    continue
    except Exception:
        pass
    return result