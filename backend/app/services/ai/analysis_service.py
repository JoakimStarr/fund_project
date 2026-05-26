import json
from datetime import datetime
from sqlalchemy import select
from app.core.database import async_session
from app.models.ai_cache import AiAnalysisCache
from app.schemas.ai_analysis import AiAnalysisResponse
from app.services.ai.provider_router import ProviderRouter
from app.services.fund.profile_service import get_fund_profile
from app.services.ai.templates.base import BaseTemplate
from app.services.ai.templates.equity import EquityTemplate
from app.services.ai.templates.bond import BondTemplate
from app.services.ai.templates.index import IndexTemplate
from app.services.ai.templates.mixed import MixedTemplate


_TEMPLATE_MAP = {
    "equity_active": EquityTemplate,
    "hybrid_equity": EquityTemplate,
    "hybrid_balanced": MixedTemplate,
    "hybrid_flexible": MixedTemplate,
    "hybrid_bond": MixedTemplate,
    "bond_pure": BondTemplate,
    "bond_mixed": BondTemplate,
    "bond_convertible": BondTemplate,
    "index_equity": IndexTemplate,
    "index_bond": IndexTemplate,
    "fof": MixedTemplate,
    "qdii": EquityTemplate,
}


def _get_template(fund_type: str) -> BaseTemplate:
    template_cls = _TEMPLATE_MAP.get(fund_type, BaseTemplate)
    return template_cls()


async def get_analysis(fund_code: str, session, context: dict = None, refresh: bool = False) -> AiAnalysisResponse:
    today = datetime.now().strftime("%Y-%m-%d")
    if not refresh:
        cached_result = await session.execute(
            select(AiAnalysisCache).where(AiAnalysisCache.fund_code == fund_code, AiAnalysisCache.trade_date == today)
        )
        cached = cached_result.scalar_one_or_none()
        if cached:
            data = json.loads(cached.analysis_json)
            data["cached"] = True
            return data
    profile = await get_fund_profile(fund_code)
    fund_type = profile.get("fund_type", "hybrid_equity")
    fund_name = profile.get("fund_name", "")
    import asyncio
    news_items = []
    holdings_data = {"codes": [], "summary": ""}
    try:
        from app.services.data.news_service import get_news
        from app.services.data.holdings_service import get_latest_holdings
        news_coro = get_news(fund_code, holdings_limit=3)
        holdings_coro = get_latest_holdings(fund_code)
        news_result, holdings_result = await asyncio.gather(news_coro, holdings_coro, return_exceptions=True)
        if not isinstance(news_result, Exception) and news_result:
            news_items = news_result[:3]
        if not isinstance(holdings_result, Exception) and holdings_result is not None:
            code_col = next((c for c in ["股票代码", "stock_code", "代码", "code"] if c in holdings_result.columns), None)
            name_col = next((c for c in ["股票名称", "stock_name", "名称", "name"] if c in holdings_result.columns), None)
            weight_col = next((c for c in ["占净值比例", "占净值比例(%)", "比例", "weight"] if c in holdings_result.columns), None)
            if code_col is not None:
                top5 = holdings_result.head(5)
                codes = []
                details = []
                for _, r in top5.iterrows():
                    code = str(r[code_col]).strip().zfill(6)
                    name = str(r[name_col]) if name_col else code
                    weight = f"{float(r[weight_col]):.1f}%" if weight_col else ""
                    codes.append(code)
                    details.append(f"{name}({weight})")
                holdings_data = {"codes": codes, "summary": "; ".join(details)}
    except Exception:
        pass
    template = _get_template(fund_type)
    messages = template.build_prompt(fund_data={"fund_code": fund_code, "fund_name": fund_name, "fund_type": fund_type}, news_data=news_items, holdings_data=holdings_data)
    router = ProviderRouter()
    result = await router.route_request(messages)
    analysis_data = result["content"]
    if isinstance(analysis_data, dict):
        analysis_data["disclaimer"] = "以上分析由AI生成，仅供参考，不构成投资建议"
    response = AiAnalysisResponse(fund_code=fund_code, trade_date=today, analysis=analysis_data, news_used=news_items if news_items else None, holdings_freshness=None, provider_used=result.get("provider"), model_used=result.get("model"), tokens_used=result.get("tokens", 0), cached=False, generated_at=datetime.now().isoformat())
    existing = await session.execute(
        select(AiAnalysisCache).where(AiAnalysisCache.fund_code == fund_code, AiAnalysisCache.trade_date == today)
    )
    existing_record = existing.scalar_one_or_none()
    if existing_record:
        existing_record.analysis_json = response.model_dump_json()
        existing_record.provider_used = result.get("provider")
        existing_record.model_used = result.get("model")
        existing_record.tokens_used = result.get("tokens", 0)
    else:
        session.add(AiAnalysisCache(fund_code=fund_code, trade_date=today, analysis_json=response.model_dump_json(), provider_used=result.get("provider"), model_used=result.get("model"), tokens_used=result.get("tokens", 0), news_count=len(news_items)))
    await session.flush()
    return response