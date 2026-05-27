import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from sqlalchemy import select
from app.core.database import async_session
from app.models.fund_nav import FundNav

logger = logging.getLogger(__name__)

REGRESSION_WINDOW = 20
FUSION_WINDOW = 30
_executor = ThreadPoolExecutor(max_workers=2)

INDEX_CANDIDATES = {
    "000300": "hs300",
    "399001": "szczs",
    "399006": "cyb",
    "000688": "kcb50",
    "000905": "zz500",
    "000852": "zz1000",
    "000016": "sz50",
}

INDEX_SINA_CODES = {
    "000300": "sh000300",
    "399001": "sz399001",
    "399006": "sz399006",
    "000688": "sh000688",
    "000905": "sh000905",
    "000852": "sh000852",
    "000016": "sh000016",
}


def _get_market_session():
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    if weekday >= 5:
        return {"is_trading": False, "session": "closed", "note": "非交易日"}
    if (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute <= 30):
        return {"is_trading": True, "session": "morning", "note": "上午交易时段"}
    if (hour == 11 and minute > 30) or (hour == 12) or (hour == 13 and minute < 0):
        return {"is_trading": False, "session": "lunch_break", "note": "午间休市"}
    if hour >= 13 and (hour < 15 or (hour == 15 and minute == 0)):
        return {"is_trading": True, "session": "afternoon", "note": "下午交易时段"}
    return {"is_trading": False, "session": "closed", "note": "闭市"}


async def _load_fund_nav(fund_code: str):
    async with async_session() as s:
        result = await s.execute(
            select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
        )
        rows = result.scalars().all()
        if not rows:
            return None
        return pd.DataFrame([{"date": r.nav_date, "nav": r.nav, "acc_nav": r.acc_nav or r.nav} for r in rows])


async def _fetch_stock_realtime(codes: list) -> dict:
    import httpx
    result = {}
    if not codes:
        return result
    codes_str = ",".join([f"sh{c}" if c.startswith("6") else f"sz{c}" for c in codes])
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
                        price = float(data[3]) if data[3] else 0.0
                        prev_close = float(data[2]) if data[2] else 0.0
                        pct_change = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        result[key] = {"name": data[0], "price": price, "prev_close": prev_close, "pct_change": round(pct_change, 4)}
                except (IndexError, ValueError):
                    continue
    except Exception as e:
        logger.warning("stock_realtime_fetch_failed error=%s", e)
    return result


async def _fetch_index_realtime() -> dict:
    import httpx
    result = {}
    codes_str = ",".join(INDEX_SINA_CODES.values())
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
                    raw_key = parts[0].strip().replace("var hq_str_", "").replace("=", "")
                    clean_key = raw_key.replace("sh", "").replace("sz", "")
                    data = parts[1].strip().strip('"').split(",")
                    if len(data) >= 4 and clean_key in INDEX_CANDIDATES:
                        price = float(data[3]) if data[3] else 0.0
                        prev_close = float(data[2]) if data[2] else 0.0
                        pct_change = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        result[clean_key] = {"name": data[0], "price": price, "prev_close": prev_close, "pct_change": round(pct_change, 4)}
                except (IndexError, ValueError):
                    continue
    except Exception as e:
        logger.warning("index_realtime_fetch_failed error=%s", e)
    return result


def _path_a_holding(holdings_list, stock_prices: dict):
    meta = {"path": "holding_proxy", "available": False}
    total_return = 0.0
    total_weight = 0.0
    contributions = []
    if not holdings_list:
        return 0.0, meta, contributions
    for h in holdings_list:
        code = str(h.get("code", "")).strip().zfill(6)
        weight = float(h.get("weight", 0))
        name = h.get("name", code)
        if weight <= 0 or code not in stock_prices:
            continue
        rt = stock_prices[code]
        pct = rt.get("pct_change", 0) / 100.0
        contrib = weight * pct
        total_return += contrib
        total_weight += weight
        contributions.append({
            "rank": len(contributions) + 1,
            "code": code,
            "name": name,
            "weight": round(weight, 4),
            "pct_change": round(pct * 100, 4),
            "contribution": round(contrib, 6),
            "price": rt.get("price"),
            "prev_close": rt.get("prev_close"),
        })
    estimated_return = total_return / total_weight if total_weight > 0 else 0.0
    available = total_weight > 0.3
    meta["available"] = available
    meta["weight_coverage"] = round(total_weight, 4)
    meta["stock_count"] = len(contributions)
    return estimated_return, meta, contributions


def _path_b_index(fund_df: pd.DataFrame, index_realtime: dict):
    meta = {"path": "index_regression", "available": False}
    if fund_df is None or len(fund_df) < REGRESSION_WINDOW + 5:
        return 0.0, meta
    fund_df = fund_df.copy()
    fund_df["fund_ret"] = fund_df["acc_nav"].pct_change()
    best_coef = 0.0
    best_r2 = -np.inf
    best_idx_name = None
    best_idx_code = None
    for code, idx_name in INDEX_CANDIDATES.items():
        if code not in index_realtime:
            continue
        idx_data = index_realtime[code]
        latest_idx_pct = idx_data.get("pct_change", 0) / 100.0
        ret_col = f"{idx_name}_ret"
        if ret_col not in fund_df.columns:
            continue
        recent = fund_df.dropna(subset=["fund_ret", ret_col]).tail(REGRESSION_WINDOW)
        if len(recent) < REGRESSION_WINDOW // 2:
            continue
        X = recent[[ret_col]].values
        y = recent["fund_ret"].values
        model = LinearRegression()
        model.fit(X, y)
        r2 = model.score(X, y)
        if r2 > best_r2:
            best_r2 = r2
            best_coef = model.coef_[0]
            best_idx_name = idx_name
            best_idx_code = code
    if best_idx_code is None or pd.isna(best_coef):
        return 0.0, meta
    estimated_return = best_coef * (index_realtime[best_idx_code].get("pct_change", 0) or 0) / 100.0
    meta["available"] = True
    meta["regression_index"] = best_idx_name
    meta["beta"] = round(float(best_coef), 4)
    meta["r2"] = round(float(best_r2), 4)
    meta["window"] = REGRESSION_WINDOW
    return estimated_return, meta


def _compute_fusion_weights(fund_df: pd.DataFrame) -> tuple:
    if fund_df is None or len(fund_df) < FUSION_WINDOW + 5:
        return 0.6, 0.4
    fund_df = fund_df.copy()
    fund_df["fund_ret"] = fund_df["acc_nav"].pct_change()
    path_a_errors = []
    path_b_errors = []
    for i in range(FUSION_WINDOW):
        try:
            cutoff = len(fund_df) - (FUSION_WINDOW - i)
            if cutoff < REGRESSION_WINDOW + 5:
                continue
            actual_ret = float(fund_df.iloc[cutoff - 1]["fund_ret"]) if pd.notna(fund_df.iloc[cutoff - 1]["fund_ret"]) else 0.0
            hist_df = fund_df.iloc[:cutoff]
            ret_b = 0.0
            best_b_coef = 0.0
            best_b_r2 = -np.inf
            for code, idx_name in INDEX_CANDIDATES.items():
                ret_col = f"{idx_name}_ret"
                if ret_col not in hist_df.columns:
                    continue
                recent = hist_df.dropna(subset=["fund_ret", ret_col]).tail(REGRESSION_WINDOW)
                if len(recent) < REGRESSION_WINDOW // 2:
                    continue
                X = recent[[ret_col]].values
                y = recent["fund_ret"].values
                m = LinearRegression()
                m.fit(X, y)
                r2 = m.score(X, y)
                if r2 > best_b_r2:
                    best_b_r2 = r2
                    best_b_coef = m.coef_[0]
            ret_b = best_b_coef * 0.001
            ret_a = 0.0
            if actual_ret != 0:
                ret_a = actual_ret * 0.8
            path_a_errors.append((ret_a - actual_ret) ** 2)
            path_b_errors.append((ret_b - actual_ret) ** 2)
        except Exception:
            continue
    err_a = np.mean(path_a_errors) if path_a_errors else 1.0
    err_b = np.mean(path_b_errors) if path_b_errors else 1.0
    total_inv = 1.0 / (err_a + 1e-8) + 1.0 / (err_b + 1e-8)
    w_a = (1.0 / (err_a + 1e-8)) / total_inv
    w_b = (1.0 / (err_b + 1e-8)) / total_inv
    return float(w_a), float(w_b)


def _compute_confidence(path_a_available, path_b_available, w_a, w_b, path_a_meta, path_b_meta):
    score = 0.3
    if path_a_available and path_b_available:
        score += 0.3
    elif path_a_available or path_b_available:
        score += 0.15
    r2_a = path_a_meta.get("proxy_r2") if isinstance(path_a_meta.get("proxy_r2"), (int, float)) else None
    if r2_a and not pd.isna(r2_a):
        score += min(0.2, float(r2_a) * 0.3)
    r2_b = path_b_meta.get("r2")
    if r2_b and not pd.isna(r2_b):
        score += min(0.2, float(r2_b) * 0.3)
    balance = 1.0 - abs(w_a - w_b)
    score += balance * 0.1
    return min(1.0, max(0.0, round(score, 3)))


async def estimate_t_day(fund_code: str, session=None, mode: str = "auto", save_result: bool = False) -> dict:
    market_session = _get_market_session()
    fund_df = await _load_fund_nav(fund_code)
    if fund_df is None or len(fund_df) < 10:
        raise ValueError(f"基金 {fund_code} 无足够净值数据")
    last_row = fund_df.iloc[-1]
    prev_nav = float(last_row["nav"])
    last_date = str(last_row["date"])
    fund_name = ""
    fund_type = "hybrid_equity"
    if session:
        from app.services.fund.profile_service import get_profile as get_fund_profile
        profile = await get_fund_profile(fund_code, session)
        if profile:
            fund_name = profile.get("fund_name", "")
            fund_type = profile.get("fund_type", "hybrid_equity")
    holdings_list = []
    if session:
        from app.services.data.holdings_service import get_latest_holdings
        try:
            hdf = await get_latest_holdings(fund_code, session)
            if hdf is not None and not hdf.empty:
                code_col = next((c for c in ["股票代码", "stock_code", "代码", "code"] if c in hdf.columns), None)
                name_col = next((c for c in ["股票名称", "stock_name", "名称", "name"] if c in hdf.columns), None)
                weight_col = next((c for c in ["占净值比例", "占净值比例(%)", "比例", "weight"] if c in hdf.columns), None)
                if code_col and name_col:
                    for _, r in hdf.head(10).iterrows():
                        w = float(r[weight_col]) / 100.0 if weight_col and pd.notna(r.get(weight_col)) else 0
                        holdings_list.append({"code": str(r[code_col]).strip().zfill(6), "name": str(r[name_col]) if name_col else "", "weight": w})
        except Exception as e:
            logger.debug("holdings_load_failed fund=%s error=%s", fund_code, e)
    import asyncio
    stock_codes = [h["code"] for h in holdings_list if h.get("weight", 0) > 0]
    stock_prices = await _fetch_stock_realtime(stock_codes)
    index_realtime = await _fetch_index_realtime()

    def _sync_paths():
        ret_a, meta_a, contributions = _path_a_holding(holdings_list, stock_prices)
        ret_b, meta_b = _path_b_index(fund_df, index_realtime)
        w_a, w_b = _compute_fusion_weights(fund_df)
        fused_ret = w_a * ret_a + w_b * ret_b
        confidence = _compute_confidence(meta_a.get("available"), meta_b.get("available"), w_a, w_b, meta_a, meta_b)
        return ret_a, ret_b, w_a, w_b, fused_ret, confidence, meta_a, meta_b, contributions

    loop = asyncio.get_running_loop()
    ret_a, ret_b, w_a, w_b, fused_ret, confidence, meta_a, meta_b, contributions = await loop.run_in_executor(_executor, _sync_paths)
    estimated_nav = prev_nav * (1 + fused_ret)
    result = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "prev_nav": round(prev_nav, 4),
        "prev_date": last_date,
        "estimated_nav": round(estimated_nav, 6),
        "estimated_return": round(fused_ret, 6),
        "estimated_return_pct": round(fused_ret * 100, 4),
        "confidence": confidence,
        "market_session": market_session,
        "method": "dual_path_fusion",
        "method_display": "双路径融合法",
        "path_a": {
            "return": round(ret_a, 6),
            "return_pct": round(ret_a * 100, 4),
            "available": meta_a.get("available", False),
            "meta": meta_a,
        },
        "path_b": {
            "return": round(ret_b, 6),
            "return_pct": round(ret_b * 100, 4),
            "available": meta_b.get("available", False),
            "meta": meta_b,
        },
        "fusion_weight": {"path_a": round(w_a, 4), "path_b": round(w_b, 4)},
        "holdings_used": contributions if contributions else None,
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
    }
    if save_result and session:
        await _save_estimation(session, fund_code, result)
    return result


async def _save_estimation(session, fund_code: str, result: dict):
    from datetime import date
    from app.models.prediction import Prediction
    today = date.today().isoformat()
    confidence = result.get("confidence", 0.5)
    direction = "up" if result["estimated_return"] > 0 else "down" if result["estimated_return"] < 0 else "neutral"
    direction_prob = min(0.95, max(0.05, 0.5 + abs(result["estimated_return"]) * 10))
    pred = Prediction(
        fund_code=fund_code,
        predict_date=today,
        target_date=today,
        predicted_return=result["estimated_return"],
        lower_bound=result["estimated_return"] - 0.02,
        upper_bound=result["estimated_return"] + 0.02,
        direction=direction,
        direction_prob=direction_prob,
        confidence_level=confidence,
        model_type="t_day_fusion",
        features_used=len(result.get("holdings_used", [])) + (1 if result.get("path_b", {}).get("available") else 0),
        fund_type=result.get("fund_type", "hybrid_equity"),
    )
    session.add(pred)
    await session.flush()
