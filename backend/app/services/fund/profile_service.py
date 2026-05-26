import json
import logging
import asyncio
from sqlalchemy import select, func
from app.models.fund_profile import FundProfileCache
from app.services.fund.routing_service import classify

logger = logging.getLogger(__name__)


async def get_profile(fund_code: str, session):
    result = await session.execute(
        select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
    )
    cached = result.scalar_one_or_none()
    if cached:
        profile = {
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
    else:
        try:
            from app.services.data.danjuan_client import get_fund_info as dj_get_info
            dj_data = await dj_get_info(fund_code)
            fund_name = dj_data.get("fund_name", "")
            fund_type_raw = ""
            benchmark = ""
            invest_strategy = ""
            company = dj_data.get("keeper_name", "")
            manager = dj_data.get("manager_name", "")
            established = dj_data.get("found_date", "")
            full_name = dj_data.get("full_name", "")
        except Exception as e:
            logger.warning(f"danjuan获取失败 {fund_code}: {e}, 尝试akshare")
            import akshare as ak
            df = ak.fund_individual_basic_info_xq(symbol=fund_code)
            if df is None or df.empty:
                raise ValueError(f"基金 {fund_code} 信息获取失败")
            row = df.iloc[0]
            fund_name = str(row.get("基金简称", ""))
            fund_type_raw = str(row.get("基金类型", ""))
            benchmark = str(row.get("业绩比较基准", ""))
            invest_strategy = str(row.get("投资策略", "") or row.get("投资目标", ""))
            company = str(row.get("基金公司", ""))
            manager = str(row.get("基金经理", ""))
            established = str(row.get("成立时间", ""))
            full_name = ""
        classification = classify(fund_name, fund_type_raw, benchmark, invest_strategy)
        fund_type = classification["fund_type"]
        skip_prediction = 1 if fund_type == "money_market" else 0
        profile = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "full_name": full_name,
            "fund_type_raw": fund_type_raw,
            "fund_type": fund_type,
            "classification_confidence": classification["confidence"],
            "established": established,
            "size_text": "",
            "company": company,
            "manager": manager,
            "benchmark": benchmark,
            "invest_strategy": invest_strategy,
            "rating": "",
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
                full_name=full_name,
                fund_type_raw=fund_type_raw,
                fund_type=fund_type,
                classification_confidence=classification["confidence"],
                established=profile["established"],
                size_text=profile["size_text"],
                company=company,
                manager=manager,
                benchmark=benchmark,
                invest_strategy=invest_strategy,
                rating=profile["rating"],
                skip_prediction=skip_prediction,
                profile_json=json.dumps(profile, ensure_ascii=False),
            ))
        await session.commit()
    from app.models.fund_nav import FundNav
    nav_result = await session.execute(
        select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date.desc()).limit(1)
    )
    latest_nav_row = nav_result.scalar_one_or_none()
    if latest_nav_row:
        profile["latest_nav"] = float(latest_nav_row.nav)
        profile["acc_nav"] = float(latest_nav_row.acc_nav) if latest_nav_row.acc_nav else None
        profile["nav_date"] = str(latest_nav_row.nav_date)
    else:
        profile["latest_nav"] = None
        profile["acc_nav"] = None
        profile["nav_date"] = None
    try:
        from app.services.data.holdings_service import get_latest_holdings
        holdings_df = await get_latest_holdings(fund_code)
        if holdings_df is not None and len(holdings_df) > 0:
            code_col = next((c for c in ["股票代码", "stock_code", "代码", "code"] if c in holdings_df.columns), None)
            name_col = next((c for c in ["股票名称", "stock_name", "名称", "name"] if c in holdings_df.columns), None)
            weight_col = next((c for c in ["占净值比例", "占净值比例(%)", "比例", "weight"] if c in holdings_df.columns), None)
            if code_col and name_col:
                holdings_list = []
                for _, r in holdings_df.head(10).iterrows():
                    w = float(r[weight_col]) / 100.0 if weight_col and r.get(weight_col) else 0
                    holdings_list.append({
                        "name": str(r[name_col]) if name_col else str(r.get(code_col, "")),
                        "code": str(r[code_col]).strip().zfill(6) if code_col else "",
                        "weight": w,
                        "change": None
                    })
                profile["holdings"] = holdings_list
            else:
                profile["holdings"] = []
        else:
            profile["holdings"] = []
    except Exception:
        profile["holdings"] = []
    try:
        from app.services.model.versioning import load_model
        _model_data, model_metrics, _features = load_model(fund_code)
        if model_metrics:
            profile["prediction_capability"] = {
                "direction_accuracy": model_metrics.get("valid_direction_accuracy"),
                "mae": model_metrics.get("valid_mae"),
                "model_version": model_metrics.get("model_version"),
                "best_model": model_metrics.get("best_model"),
                "train_rows": model_metrics.get("train_rows"),
            }
        else:
            profile["prediction_capability"] = None
    except Exception:
        profile["prediction_capability"] = None
    from sqlalchemy import func
    nav_count_result = await session.execute(select(func.count(FundNav.id)).where(FundNav.fund_code == fund_code))
    total_nav_rows = nav_count_result.scalar() or 0
    profile["data_days"] = total_nav_rows
    return profile