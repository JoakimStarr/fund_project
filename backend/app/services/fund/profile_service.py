import json
import logging
import akshare as ak
from sqlalchemy import select
from app.models.fund_profile import FundProfileCache
from app.services.fund.routing_service import classify

logger = logging.getLogger(__name__)


async def get_profile(fund_code: str, session):
    result = await session.execute(
        select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
    )
    cached = result.scalar_one_or_none()
    if cached:
        return {
            "fund_code": cached.fund_code,
            "fund_name": cached.fund_name,
            "full_name": cached.full_name,
            "fund_type_raw": cached.fund_type_raw,
            "fund_type": cached.fund_type,
            "classification_confidence": cached.classification_confidence,
            "established": cached.established,
            "size_text": cached.size_text,
            "company": cached.company,
            "manager": cached.manager,
            "benchmark": cached.benchmark,
            "invest_strategy": cached.invest_strategy,
            "rating": cached.rating,
            "skip_prediction": bool(cached.skip_prediction),
        }
    df = ak.fund_individual_basic_info_xq(symbol=fund_code)
    if df is None or df.empty:
        raise ValueError(f"基金 {fund_code} 信息获取失败")
    row = df.iloc[0]
    fund_name = str(row.get("基金简称", ""))
    fund_type_raw = str(row.get("基金类型", ""))
    benchmark = str(row.get("业绩比较基准", ""))
    invest_strategy = str(row.get("投资策略", "") or row.get("投资目标", ""))
    classification = classify(fund_name, fund_type_raw, benchmark, invest_strategy)
    fund_type = classification["fund_type"]
    skip_prediction = 1 if fund_type == "money_market" else 0
    profile = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type_raw": fund_type_raw,
        "fund_type": fund_type,
        "classification_confidence": classification["confidence"],
        "established": str(row.get("成立时间", "")),
        "size_text": str(row.get("最新规模", "")),
        "company": str(row.get("基金公司", "")),
        "manager": str(row.get("基金经理", "")),
        "benchmark": benchmark,
        "invest_strategy": invest_strategy,
        "rating": str(row.get("基金评级", "")),
        "skip_prediction": skip_prediction,
    }
    existing = await session.execute(
        select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
    )
    existing_record = existing.scalar_one_or_none()
    if existing_record:
        for key, val in profile.items():
            if key != "fund_code":
                setattr(existing_record, key, val)
        existing_record.profile_json = json.dumps(profile, ensure_ascii=False)
    else:
        session.add(FundProfileCache(
            fund_code=fund_code,
            fund_name=fund_name,
            fund_type_raw=fund_type_raw,
            fund_type=fund_type,
            classification_confidence=classification["confidence"],
            established=profile["established"],
            size_text=profile["size_text"],
            company=profile["company"],
            manager=profile["manager"],
            benchmark=benchmark,
            invest_strategy=invest_strategy,
            rating=profile["rating"],
            skip_prediction=skip_prediction,
            profile_json=json.dumps(profile, ensure_ascii=False),
        ))
    await session.commit()
    return profile