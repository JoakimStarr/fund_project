import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from app.core.logging_config import set_log_context
from app.services.data_service import get_fund_nav, load_market_data
from app.services.proxy_portfolio_service import build_top10_proxy

logger = logging.getLogger(__name__)

_intraday_cache: dict[str, dict] = {}
REGRESSION_WINDOW = 20
FUSION_WINDOW = 30


def _get_path_a_return(fund_code: str) -> tuple[float, dict]:
    """
    路径A：持仓映射法 — 通过代理组合收益估算当日盘中涨跌幅。
    调用 proxy_portfolio_service 获取top10持仓代理组合的当日收益率。
    """
    meta = {"path": "holding_proxy", "available": False}
    try:
        proxy_df, proxy_meta = build_top10_proxy(fund_code)
        if proxy_df.empty or "top10_proxy_ret" not in proxy_df.columns:
            logger.warning("intraday_path_a_unavailable fund_code=%s reason=no_proxy_data", fund_code)
            return 0.0, meta

        latest = proxy_df.iloc[-1]
        ret = float(latest.get("top10_proxy_ret", np.nan))
        if pd.isna(ret):
            logger.warning("intraday_path_a_nan fund_code=%s", fund_code)
            return 0.0, meta

        meta["available"] = True
        meta["proxy_status"] = proxy_meta.get("top10_proxy_status", "unknown")
        meta["proxy_r2"] = proxy_meta.get("exposure_summary", {}).get("proxy_r2_60")
        meta["available_count"] = proxy_meta.get("top10_proxy_available_count", 0)
        logger.info("intraday_path_a_success fund_code=%s ret=%.6f r2=%s", fund_code, ret, meta.get("proxy_r2"))
        return ret, meta
    except Exception as e:
        logger.exception("intraday_path_a_failed fund_code=%s error=%s", fund_code, e)
        meta["error"] = str(e)
        return 0.0, meta


def _get_path_b_return(fund_code: str) -> tuple[float, dict]:
    """
    路径B：指数回归法 — 用最近20日基金vs指数的回归系数估算当日收益。

    基于历史数据拟合基金对主要指数（沪深300/创业板）的暴露系数，
    再用今日指数实时涨跌幅加权估算基金当日收益。
    """
    meta = {"path": "index_regression", "available": False}
    try:
        fund_df, fund_meta = get_fund_nav(fund_code, require_fresh=False)
        indexes, index_meta = load_market_data(require_fresh=False)

        if fund_df.empty or len(fund_df) < REGRESSION_WINDOW + 5:
            logger.warning("intraday_path_b_insufficient fund_code=%s rows=%s", fund_code, len(fund_df))
            return 0.0, meta

        fund_df = fund_df.copy()
        fund_df["fund_ret"] = fund_df["acc_nav"].pct_change()

        merge_cols = ["date"]
        for name, idx_df in indexes.items():
            idx_copy = idx_df[["date", "close"]].copy()
            idx_copy[f"{name}_ret"] = idx_copy["close"].pct_change()
            fund_df = fund_df.merge(idx_copy[["date", f"{name}_ret"]], on="date", how="left")

        candidate_index_cols = [c for c in fund_df.columns if c.endswith("_ret") and c != "fund_ret"]
        if not candidate_index_cols:
            logger.warning("intraday_path_b_no_index fund_code=%s", fund_code)
            return 0.0, meta

        recent = fund_df.dropna(subset=["fund_ret"] + candidate_index_cols).tail(REGRESSION_WINDOW)
        if len(recent) < REGRESSION_WINDOW // 2:
            logger.warning("intraday_path_b_not_enough_samples fund_code=%s samples=%s", fund_code, len(recent))
            return 0.0, meta

        best_col = None
        best_r2 = -np.inf
        best_coef = 0.0
        for col in candidate_index_cols[:3]:
            X = recent[[col]].values
            y = recent["fund_ret"].values
            model = LinearRegression()
            model.fit(X, y)
            r2 = model.score(X, y)
            if r2 > best_r2:
                best_r2 = r2
                best_col = col
                best_coef = model.coef_[0]

        if best_col is None or pd.isna(best_coef):
            return 0.0, meta

        index_name = best_col.replace("_ret", "")
        latest_idx = indexes.get(index_name)
        if latest_idx is None or latest_idx.empty:
            return 0.0, meta

        # 修复 Bug: 正确计算指数最新收益率（需要至少2条记录）
        if len(latest_idx) < 2:
            last_idx_ret = 0.0
        else:
            close_series = latest_idx["close"].tail(2)
            prev_close = float(close_series.iloc[0])
            curr_close = float(close_series.iloc[1])
            last_idx_ret = (curr_close - prev_close) / prev_close if prev_close != 0 else 0.0

        estimated_ret = best_coef * last_idx_ret

        meta["available"] = True
        meta["regression_index"] = index_name
        meta["beta"] = round(float(best_coef), 4)
        meta["r2"] = round(float(best_r2), 4)
        meta["window"] = REGRESSION_WINDOW
        meta["latest_index_ret"] = round(last_idx_ret, 6)

        logger.info(
            "intraday_path_b_success fund_code=%s estimated=%.6f beta=%.4f r2=%.4f index=%s",
            fund_code, estimated_ret, best_coef, best_r2, index_name,
        )
        return estimated_ret, meta
    except Exception as e:
        logger.exception("intraday_path_b_failed fund_code=%s error=%s", fund_code, e)
        meta["error"] = str(e)
        return 0.0, meta


def _compute_fusion_weight(fund_code: str) -> tuple[float, float]:
    """
    动态融合权重计算：基于近30日各路径误差反比加权。

    Returns:
        (path_a_weight, path_b_weight): 两路径融合权重，和为1.0
    """
    try:
        fund_df, _ = get_fund_nav(fund_code, require_fresh=False)
        if len(fund_df) < FUSION_WINDOW + 5:
            logger.info("intraday_fusion_default_weights fund_code=%s reason=insufficient_history", fund_code)
            return 0.6, 0.4

        path_a_errors = []
        path_b_errors = []

        for i in range(FUSION_WINDOW):
            try:
                cutoff = len(fund_df) - (FUSION_WINDOW - i)
                if cutoff < REGRESSION_WINDOW + 5:
                    continue
                hist_df = fund_df.iloc[:cutoff]
                actual_ret = float(hist_df.iloc[-1].get("daily_growth_pct", 0)) / 100.0 if pd.notna(hist_df.iloc[-1].get("daily_growth_pct")) else float(hist_df["acc_nav"].pct_change().iloc[-1])

                ret_a, _ = _get_path_a_return_historical(fund_code, hist_df)
                ret_b, _ = _get_path_b_return_historical(fund_code, hist_df)

                if ret_a is not None:
                    path_a_errors.append((ret_a - actual_ret) ** 2)
                if ret_b is not None:
                    path_b_errors.append((ret_b - actual_ret) ** 2)
            except Exception:
                continue

        err_a = np.mean(path_a_errors) if path_a_errors else 1.0
        err_b = np.mean(path_b_errors) if path_b_errors else 1.0

        total_inv = 1.0 / (err_a + 1e-8) + 1.0 / (err_b + 1e-8)
        w_a = (1.0 / (err_a + 1e-8)) / total_inv
        w_b = (1.0 / (err_b + 1e-8)) / total_inv

        logger.info("intraday_fusion_weights fund_code=%s w_a=%.3f w_b=%.3f err_a=%.6f err_b=%.6f", fund_code, w_a, w_b, err_a, err_b)
        return float(w_a), float(w_b)
    except Exception as e:
        logger.warning("intraday_fusion_weight_error fund_code=%s using_default error=%s", fund_code, e)
        return 0.6, 0.4


def _get_path_a_return_historical(fund_code: str, hist_df: pd.DataFrame) -> float | None:
    """历史回测用：基于历史快照计算路径A收益"""
    try:
        proxy_df, _ = build_top10_proxy(fund_code)
        if proxy_df.empty or "top10_proxy_ret" not in proxy_df.columns:
            return None
        target_date = hist_df.iloc[-1]["date"]
        match = proxy_df[proxy_df["date"] <= target_date]
        if match.empty:
            return None
        return float(match.iloc[-1].get("top10_proxy_ret", np.nan))
    except Exception:
        return None


def _get_path_b_return_historical(fund_code: str, hist_df: pd.DataFrame) -> float | None:
    """历史回测用：基于历史快照计算路径B收益"""
    try:
        indexes, _ = load_market_data(require_fresh=False)
        fund_df = hist_df.copy()
        fund_df["fund_ret"] = fund_df["acc_nav"].pct_change()
        for name, idx_df in indexes.items():
            idx_copy = idx_df[["date", "close"]].copy()
            idx_copy[f"{name}_ret"] = idx_copy["close"].pct_change()
            fund_df = fund_df.merge(idx_copy[["date", f"{name}_ret"]], on="date", how="left")

        candidate_index_cols = [c for c in fund_df.columns if c.endswith("_ret") and c != "fund_ret"]
        if not candidate_index_cols:
            return None

        recent = fund_df.dropna(subset=["fund_ret"] + candidate_index_cols).tail(REGRESSION_WINDOW)
        if len(recent) < REGRESSION_WINDOW // 2:
            return None

        best_r2 = -np.inf
        best_coef = 0.0
        best_col = None
        for col in candidate_index_cols[:3]:
            X = recent[[col]].values
            y = recent["fund_ret"].values
            model = LinearRegression()
            model.fit(X, y)
            r2 = model.score(X, y)
            if r2 > best_r2:
                best_r2 = r2
                best_coef = model.coef_[0]
                best_col = col

        if best_col is None:
            return None

        index_name = best_col.replace("_ret", "")
        latest_idx = indexes.get(index_name)
        if latest_idx is None or latest_idx.empty:
            return None

        target_date = hist_df.iloc[-1]["date"]
        idx_match = latest_idx[latest_idx["date"] <= target_date]
        if idx_match.empty:
            return None
        last_idx_ret = float(idx_match.iloc[-1]["close"].pct_change()) if len(idx_match) > 1 else 0.0
        return best_coef * last_idx_ret
    except Exception:
        return None


def _compute_confidence(path_a_available: bool, path_b_available: bool, w_a: float, w_b: float,
                        path_a_meta: dict, path_b_meta: dict) -> float:
    """
    综合置信度评估：
    - 双路径可用 > 单路径可用 > 无路径
    - R²越高置信度越高
    - 权重越均衡说明信息互补性越强
    """
    score = 0.3

    if path_a_available and path_b_available:
        score += 0.3
    elif path_a_available or path_b_available:
        score += 0.15

    r2_a = path_a_meta.get("proxy_r2")
    if r2_a and not pd.isna(r2_a):
        score += min(0.2, float(r2_a) * 0.3)

    r2_b = path_b_meta.get("r2")
    if r2_b and not pd.isna(r2_b):
        score += min(0.2, float(r2_b) * 0.3)

    balance = 1.0 - abs(w_a - w_b)
    score += balance * 0.1

    return min(1.0, max(0.0, round(score, 3)))


def estimate_intraday_nav(fund_code: str) -> dict:
    """
    T日盘中净值估算服务 — 双路径融合估算策略（§4.1）。

    路径A：持仓映射（代理组合收益）
    路径B：指数回归（最近20日基金vs指数回归系数）
    动态融合权重基于近30日各路径误差

    Args:
        fund_code: 基金代码

    Returns:
        包含 estimated_nav, holding_path_return, index_path_return,
             fusion_weight, confidence 等字段的字典
    """
    set_log_context(fund_code=fund_code, stage="intraday_estimate_start")
    logger.info("intraday_estimate_start fund_code=%s", fund_code)

    try:
        fund_df, fund_meta = get_fund_nav(fund_code, require_fresh=False)
        if fund_df.empty:
            raise ValueError("无法获取基金净值数据")

        last_nav = float(fund_df.iloc[-1]["nav"])
        last_date = str(fund_df.iloc[-1]["date"])

        path_a_ret, path_a_meta = _get_path_a_return(fund_code)
        path_b_ret, path_b_meta = _get_path_b_return(fund_code)

        w_a, w_b = _compute_fusion_weight(fund_code)
        fused_ret = w_a * path_a_ret + w_b * path_b_ret
        estimated_nav = last_nav * (1 + fused_ret)

        confidence = _compute_confidence(
            path_a_meta.get("available", False),
            path_b_meta.get("available", False),
            w_a, w_b, path_a_meta, path_b_meta,
        )

        result = {
            "fund_code": fund_code,
            "last_nav": round(last_nav, 4),
            "last_date": last_date,
            "estimated_nav": round(estimated_nav, 4),
            "estimated_change_pct": round(fused_ret * 100, 4),
            "holding_path_return": round(path_a_ret, 6),
            "holding_path_meta": path_a_meta,
            "index_path_return": round(path_b_ret, 6),
            "index_path_meta": path_b_meta,
            "fusion_weight": {
                "path_a": round(w_a, 4),
                "path_b": round(w_b, 4),
            },
            "confidence": confidence,
            "estimated_at": datetime.now().isoformat(timespec="seconds"),
            "nav_source": fund_meta.get("source_used"),
        }

        _intraday_cache[fund_code] = result
        set_log_context(stage="intraday_estimate_success")
        logger.info(
            "intraday_estimate_success fund_code=%s nav=%.4f est_nav=%.4f change=%.4f%% conf=%.2f",
            fund_code, last_nav, estimated_nav, fused_ret * 100, confidence,
        )
        return result
    except Exception as e:
        set_log_context(stage="intraday_estimate_failed")
        logger.exception("intraday_estimate_failed fund_code=%s error=%s", fund_code, e)
        return {
            "fund_code": fund_code,
            "ok": False,
            "error": str(e),
            "estimated_at": datetime.now().isoformat(timespec="seconds"),
        }


def get_latest_intraday_estimate(fund_code: str) -> dict | None:
    """获取最新的盘中估算缓存结果"""
    cached = _intraday_cache.get(fund_code)
    if cached is None:
        return None
    result = dict(cached)
    result["from_cache"] = True
    return result
