import json
import logging
from sqlalchemy import select, func
from app.models.fund_profile import FundProfileCache
from app.services.fund.routing_service import classify

logger = logging.getLogger(__name__)


async def _fetch_akshare_info(fund_code: str) -> dict:
    import akshare as ak
    df = ak.fund_individual_basic_info_xq(symbol=fund_code)
    if df is None or df.empty:
        raise ValueError(f"akshare无数据 {fund_code}")
    info_map = {}
    for _, row in df.iterrows():
        info_map[str(row.iloc[0])] = str(row.iloc[1])
    return {
        "fund_name": info_map.get("基金简称", ""),
        "full_name": info_map.get("基金全称", ""),
        "fund_type_raw": info_map.get("基金类型", ""),
        "company": info_map.get("基金公司", ""),
        "manager": info_map.get("基金经理", ""),
        "established": info_map.get("成立时间", ""),
        "size_text": info_map.get("最新规模", ""),
        "benchmark": info_map.get("业绩比较基准", ""),
        "invest_strategy": info_map.get("投资策略", "") or info_map.get("投资目标", ""),
        "custodian_bank": info_map.get("托管银行", ""),
        "rating_agency": info_map.get("评级机构", ""),
        "rating": info_map.get("基金评级", ""),
    }


async def _fetch_danjuan_info(fund_code: str) -> dict:
    from app.services.data.danjuan_client import get_fund_info
    data = await get_fund_info(fund_code)
    return {
        "fund_name": data.get("fund_name", ""),
        "full_name": data.get("full_name", ""),
        "company": data.get("keeper_name", ""),
        "manager": data.get("manager_name", ""),
        "established": data.get("found_date", ""),
        "size_text": data.get("totshare", ""),
        "type_desc": data.get("type_desc", ""),
        "rating": data.get("rating_desc", ""),
        "risk_level": data.get("risk_level"),
        "style_tips": data.get("style_tips", ""),
        "custodian_bank": data.get("trup_name", ""),
        "nav_grtd": data.get("nav_grtd"),
        "nav_grl1m": data.get("nav_grl1m"),
        "nav_grl3m": data.get("nav_grl3m"),
        "nav_grl6m": data.get("nav_grl6m"),
        "nav_grlty": data.get("nav_grlty"),
        "nav_grl1y": data.get("nav_grl1y"),
        "nav_grl3y": data.get("nav_grl3y"),
        "nav_grl5y": data.get("nav_grl5y"),
        "benchmark": data.get("performance_bench_mark", ""),
        "invest_orientation": data.get("invest_orientation", ""),
        "invest_target": data.get("invest_target", ""),
        "follower_count": data.get("follower_count"),
    }


async def _fetch_asset_allocation(fund_code: str) -> list:
    from app.services.data.danjuan_client import get_asset_percent
    try:
        data = await get_asset_percent(fund_code)
        items = data.get("items", [])
        if not items:
            return []
        result = []
        for item in items:
            pct = item.get("percent")
            try:
                pct_val = float(pct) / 100.0 if pct else 0
            except (ValueError, TypeError):
                pct_val = 0
            result.append({
                "name": item.get("name", ""),
                "code": (item.get("code") or "").strip().zfill(6),
                "weight": round(pct_val, 6),
                "type_code": item.get("type_code", ""),
            })
        return sorted(result, key=lambda x: x["weight"], reverse=True)
    except Exception as e:
        logger.debug("asset_alloc_fetch_failed fund=%s error=%s", fund_code, e)
        return []


async def get_profile(fund_code: str, session):
    result = await session.execute(
        select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
    )
    cached = result.scalar_one_or_none()
    if cached:
        extra = {}
        if cached.profile_json:
            try:
                extra = json.loads(cached.profile_json)
            except (json.JSONDecodeError, TypeError):
                pass
        profile = {
            "fund_code": cached.fund_code,
            "fund_name": cached.fund_name,
            "full_name": cached.full_name,
            "fund_type_raw": cached.fund_type_raw,
            "fund_type": cached.fund_type,
            "classification_confidence": cached.classification_confidence,
            "established": cached.established,
            "size_text": cached.size_text or extra.get("size_text", ""),
            "company": cached.company,
            "manager": cached.manager,
            "benchmark": cached.benchmark,
            "invest_strategy": cached.invest_strategy,
            "rating": cached.rating or extra.get("rating", ""),
            "skip_prediction": bool(cached.skip_prediction),
            "risk_level": extra.get("risk_level"),
            "style_tips": extra.get("style_tips", ""),
            "custodian_bank": extra.get("custodian_bank", ""),
            "type_desc": extra.get("type_desc", ""),
            "nav_grtd": extra.get("nav_grtd"),
            "nav_grl1m": extra.get("nav_grl1m"),
            "nav_grl3m": extra.get("nav_grl3m"),
            "nav_grl6m": extra.get("nav_grl6m"),
            "nav_grlty": extra.get("nav_grlty"),
            "nav_grl1y": extra.get("nav_grl1y"),
            "nav_grl3y": extra.get("nav_grl3y"),
            "nav_grl5y": extra.get("nav_grl5y"),
            "follower_count": extra.get("follower_count"),
            "asset_allocation": extra.get("asset_allocation"),
            "holdings": extra.get("holdings"),
        }
    else:
        ak_info = {}
        dj_info = {}
        try:
            ak_info = await _fetch_akshare_info(fund_code)
        except Exception as e:
            logger.warning("akshare_basic_failed fund=%s error=%s", fund_code, e)
        try:
            dj_info = await _fetch_danjuan_info(fund_code)
        except Exception as e:
            logger.warning("danjuan_basic_failed fund=%s error=%s", fund_code, e)
        fund_name = dj_info.get("fund_name") or ak_info.get("fund_name", "")
        full_name = dj_info.get("full_name") or ak_info.get("full_name", "")
        company = dj_info.get("company") or ak_info.get("company", "")
        manager = dj_info.get("manager") or ak_info.get("manager", "")
        established = dj_info.get("established") or ak_info.get("established", "")
        size_text = dj_info.get("size_text") or ak_info.get("size_text", "")
        benchmark = dj_info.get("benchmark") or ak_info.get("benchmark", "")
        invest_strategy = dj_info.get("invest_orientation") or dj_info.get("invest_target") or ak_info.get("invest_strategy", "")
        fund_type_raw = dj_info.get("type_desc") or ak_info.get("fund_type_raw", "")
        rating = dj_info.get("rating") or ak_info.get("rating", "")
        risk_level = dj_info.get("risk_level")
        style_tips = dj_info.get("style_tips", "")
        custodian_bank = dj_info.get("custodian_bank") or ak_info.get("custodian_bank", "")
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
            "size_text": size_text,
            "company": company,
            "manager": manager,
            "benchmark": benchmark,
            "invest_strategy": invest_strategy,
            "rating": rating,
            "risk_level": risk_level,
            "style_tips": style_tips,
            "custodian_bank": custodian_bank,
            "skip_prediction": skip_prediction,
            "nav_grtd": dj_info.get("nav_grtd"),
            "nav_grl1m": dj_info.get("nav_grl1m"),
            "nav_grl3m": dj_info.get("nav_grl3m"),
            "nav_grl6m": dj_info.get("nav_grl6m"),
            "nav_grlty": dj_info.get("nav_grlty"),
            "nav_grl1y": dj_info.get("nav_grl1y"),
            "nav_grl3y": dj_info.get("nav_grl3y"),
            "nav_grl5y": dj_info.get("nav_grl5y"),
            "follower_count": dj_info.get("follower_count"),
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
    # 优先使用缓存中的持仓数据，如果没有再实时获取
    cached_aa = profile.get("asset_allocation")
    cached_holdings = profile.get("holdings")
    
    if cached_aa and cached_holdings:
        # 使用缓存数据
        logger.info("using_cached_asset_allocation fund=%s", fund_code)
    else:
        # 实时获取持仓数据
        asset_list = await _fetch_asset_allocation(fund_code)
        stocks = [a for a in asset_list if a.get("type_code") in ("stock", "1", "") and a.get("code")]
        bonds = [a for a in asset_list if a.get("type_code") in ("bond", "2")]
        cash = [a for a in asset_list if a.get("type_code") in ("cash", "3")]
        other = [a for a in asset_list if a not in stocks and a not in bonds and a not in cash]
        profile["holdings"] = stocks[:10]
        profile["asset_allocation"] = {
            "stocks": stocks[:10],
            "bonds": bonds[:5],
            "cash": cash[:3],
            "other": other[:5],
            "all_items": asset_list,
            "stock_total_weight": round(sum(s.get("weight", 0) for s in stocks), 4),
            "bond_total_weight": round(sum(b.get("weight", 0) for b in bonds), 4),
            "cash_total_weight": round(sum(c.get("weight", 0) for c in cash), 4),
        }
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
    nav_count_result = await session.execute(select(func.count(FundNav.id)).where(FundNav.fund_code == fund_code))
    total_nav_rows = nav_count_result.scalar() or 0
    profile["data_days"] = total_nav_rows
    return profile
