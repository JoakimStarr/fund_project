import logging
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.errors import DirectionModelError, PredictionFeatureMissingError
from app.core.logging_config import set_log_context
from app.services.feature_service import build_features, model_feature_columns
from app.services.model_registry_service import append_prediction, load_model_archive
from app.services.model_selection_service import PREDICTION_MODE

logger = logging.getLogger(__name__)


def _direction_signal(p_up: float | None) -> tuple[str, str]:
    if p_up is None:
        return "unavailable", "none"
    if p_up >= 0.65:
        return "bullish", "strong"
    if p_up >= 0.60:
        return "bullish", "weak"
    if p_up <= 0.35:
        return "bearish", "strong"
    if p_up <= 0.40:
        return "bearish", "weak"
    return "neutral", "none"


def _point_health(metrics: dict) -> dict:
    flat = bool(metrics.get("flat_prediction"))
    low_corr = bool(metrics.get("low_correlation"))
    near = bool(metrics.get("near_baseline"))
    if flat:
        message = "点预测接近均值，不能作为涨跌幅精确判断。"
    elif near:
        message = "点预测未显著优于简单均值基准。"
    else:
        message = "点预测通过基础健康检查，仍仅作辅助。"
    return {
        "flat_prediction": flat,
        "low_correlation": low_corr,
        "near_baseline": near,
        "pred_real_std_ratio": metrics.get("pred_real_std_ratio"),
        "pred_real_corr": metrics.get("pred_real_corr"),
        "model_vs_mean_improvement": metrics.get("model_vs_mean_improvement"),
        "message": message,
    }


def _direction_health(metrics: dict, signal: str) -> dict:
    available = bool(metrics.get("direction_available"))
    strong_count = metrics.get("strong_signal_count") or 0
    if not available:
        message = "方向模型不可用，本次无有效方向信号。"
    elif signal == "neutral":
        message = "方向概率优势不足，本次无有效方向信号。"
    elif strong_count < 20:
        message = "强信号样本数不足，历史胜率暂不具备统计参考价值。"
    else:
        message = "方向信号仅作条件概率参考，仍需结合区间风险。"
    return {
        "direction_available": available,
        "auc": metrics.get("auc"),
        "brier_score": metrics.get("brier_score"),
        "strong_signal_count": strong_count,
        "strong_signal_ratio": metrics.get("strong_signal_ratio"),
        "strong_signal_win_rate": metrics.get("strong_signal_win_rate"),
        "message": message,
    }


def _current_regime(latest: pd.DataFrame, interval_config: dict) -> tuple[str, bool, int]:
    vol_col = interval_config.get("vol_col", "fund_ret_std_20")
    value = latest[vol_col].iloc[0] if vol_col in latest.columns else None
    thresholds = interval_config.get("regime_thresholds", {})
    if value is None or pd.isna(value):
        regime = "mid_vol"
    elif value <= thresholds.get("low_max", float("-inf")):
        regime = "low_vol"
    elif value >= thresholds.get("high_min", float("inf")):
        regime = "high_vol"
    else:
        regime = "mid_vol"
    group_size = int((interval_config.get("group_size") or {}).get(regime, 0))
    fallback = regime not in (interval_config.get("group_quantiles") or {}) or group_size < 50
    return regime, fallback, group_size


def _intervals(pred: float, interval_config: dict, regime: str, fallback: bool) -> dict:
    quantiles = interval_config.get("global_quantiles", {})
    if not fallback:
        quantiles = (interval_config.get("group_quantiles") or {}).get(regime, quantiles)
    intervals = {}
    for level in ["70", "80", "90", "99"]:
        radius = float(quantiles.get(level) or interval_config.get("global_quantiles", {}).get(level) or 0.02)
        intervals[level] = {"lower": pred - radius, "upper": pred + radius, "width": 2 * radius, "width_bp": 2 * radius * 10000}
    width80 = intervals["80"]["width"]
    health = "normal" if width80 < 0.05 else "wide" if width80 < 0.08 else "very_wide"
    return {
        "intervals": intervals,
        "lower_70": intervals["70"]["lower"],
        "upper_70": intervals["70"]["upper"],
        "lower_80": intervals["80"]["lower"],
        "upper_80": intervals["80"]["upper"],
        "lower_90": intervals["90"]["lower"],
        "upper_90": intervals["90"]["upper"],
        "lower_99": intervals["99"]["lower"],
        "upper_99": intervals["99"]["upper"],
        "interval_health": {"status": health, "message": f"80% 区间状态：{health}"},
    }


def _safe_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _proxy_confidence(proxy_r2, point_metrics: dict) -> str:
    if proxy_r2 is not None and proxy_r2 >= 0.60 and point_metrics.get("model_vs_mean_improvement", 0) > 0.05 and point_metrics.get("pred_real_corr", 0) > 0.10:
        return "high"
    if proxy_r2 is not None and proxy_r2 >= 0.35:
        return "medium"
    return "low"


def _model_feature_names(model, fallback_cols: list[str]) -> list[str]:
    for candidate in (
        model,
        getattr(model, "estimator", None),
        getattr(getattr(model, "estimator", None), "estimator", None),
    ):
        if candidate is None:
            continue
        names = getattr(candidate, "feature_names_in_", None)
        if names is not None:
            return list(names)
        named_steps = getattr(candidate, "named_steps", None)
        if named_steps and "imputer" in named_steps:
            names = getattr(named_steps["imputer"], "feature_names_in_", None)
            if names is not None:
                return list(names)
    return fallback_cols


def _align_model_features(model, latest: pd.DataFrame, fallback_cols: list[str]) -> pd.DataFrame:
    cols = _model_feature_names(model, fallback_cols)
    aligned = latest.copy()
    for col in cols:
        if col not in aligned.columns:
            aligned[col] = 0.0
    aligned = aligned[cols].fillna(0.0)
    return aligned


def _direction_classes(model) -> list:
    for candidate in (
        model,
        getattr(model, "estimator", None),
        getattr(getattr(model, "estimator", None), "estimator", None),
    ):
        if candidate is None:
            continue
        classes = getattr(candidate, "classes_", None)
        if classes is not None:
            return [int(x) if hasattr(x, "item") else x for x in list(classes)]
    return []


def predict_next(fund_code: str, request_id: str) -> dict:
    try:
        point_model, direction_model, config, metrics, interval_config = load_model_archive(fund_code)
        data_full, _, meta = build_features(fund_code, require_fresh=False)
        feature_cols = model_feature_columns(data_full)
        latest = data_full.iloc[[-1]]
        missing_rate = float(latest[feature_cols].isna().mean(axis=1).iloc[0])
        if missing_rate > 0.35:
            raise PredictionFeatureMissingError(
                "Latest feature row has too many missing values",
                details={"missing_rate": missing_rate, "asof_date": str(latest["date"].iloc[0].date())},
            )

        point_x = _align_model_features(point_model, latest, feature_cols)
        pred = float(point_model.predict(point_x)[0])
        p_up = None
        p_down = None
        direction_classes = []
        direction_available = direction_model is not None
        direction_failure_reason = None
        if direction_model is not None:
            try:
                direction_x = _align_model_features(direction_model, latest, feature_cols)
                proba = direction_model.predict_proba(direction_x)[0]
                direction_classes = _direction_classes(direction_model)
                if 0 not in direction_classes or 1 not in direction_classes:
                    raise DirectionModelError(
                        "Direction model classes_ must contain 0 and 1",
                        details={"direction_classes": direction_classes},
                    )
                p_up = float(proba[direction_classes.index(1)])
                p_down = float(proba[direction_classes.index(0)])
            except Exception as exc:
                if isinstance(exc, DirectionModelError):
                    raise
                logger.exception("direction_predict_failed")
                direction_available = False
                direction_failure_reason = str(exc)
        if p_down is None and p_up is not None:
            p_down = 1 - p_up
        signal, strength = _direction_signal(p_up)
        regime, fallback, group_size = _current_regime(latest, interval_config)
        if fallback:
            set_log_context(stage="regime_interval_fallback")
            logger.info("regime_interval_fallback group=%s size=%s", regime, group_size)
        interval_data = _intervals(pred, interval_config, regime, fallback)

        point_metrics = metrics.get("point", metrics)
        direction_metrics = {**metrics.get("direction", {}), "direction_available": direction_available}
        if direction_failure_reason:
            direction_metrics["direction_failure_reason"] = direction_failure_reason

        today_nav = float(latest["nav"].iloc[0])
        pred_nav = today_nav * (1 + pred)
        nav_interval_80 = {"lower": today_nav * (1 + interval_data["lower_80"]), "upper": today_nav * (1 + interval_data["upper_80"])}
        nav_interval_90 = {"lower": today_nav * (1 + interval_data["lower_90"]), "upper": today_nav * (1 + interval_data["upper_90"])}
        nav_interval_99 = {"lower": today_nav * (1 + interval_data["lower_99"]), "upper": today_nav * (1 + interval_data["upper_99"])}

        proxy_r2 = _safe_float(latest["proxy_r2_60"].iloc[0]) if "proxy_r2_60" in latest.columns else None
        tracking_error = _safe_float(latest["tracking_error_60"].iloc[0]) if "tracking_error_60" in latest.columns else None
        proxy_quality = latest["proxy_quality_flag"].iloc[0] if "proxy_quality_flag" in latest.columns else "low"
        proxy_meta = meta.get("proxy") or {}
        proxy_features_helpful = bool(point_metrics.get("proxy_features_helpful") or metrics.get("proxy_features_helpful"))
        exposure_summary = proxy_meta.get("exposure_summary", {})

        result = {
            "fund_code": fund_code,
            "prediction_mode": PREDICTION_MODE,
            "prediction_target_description": "使用截至 asof_date 的基金净值和市场数据预测下一交易日收益",
            "asof_date": str(latest["date"].iloc[0].date()),
            "pred": pred,
            "pred_return": pred,
            "today_nav": today_nav,
            "pred_nav": pred_nav,
            "nav_interval_80": nav_interval_80,
            "nav_interval_90": nav_interval_90,
            "nav_interval_99": nav_interval_99,
            "p_up": p_up,
            "p_down": p_down,
            "direction_classes": direction_classes,
            "p_up_source_class": 1 if 1 in direction_classes else None,
            "p_down_source_class": 0 if 0 in direction_classes else None,
            "direction_signal": signal,
            "direction_strength": strength,
            "point_model_name": config.get("point_model_name"),
            "direction_model_name": config.get("direction_model_name"),
            "best_model": config.get("point_model_name"),
            "selector": "v2",
            "scaler": "v2",
            **interval_data,
            "residual_group_used": regime,
            "residual_group_fallback": fallback,
            "residual_group_size": group_size,
            "interval_method": interval_config.get("interval_method"),
            "proxy_available": proxy_meta.get("proxy_available", False),
            "proxy_method": proxy_meta.get("proxy_method"),
            "proxy_unavailable_reason": proxy_meta.get("reason"),
            "proxy_r2_60": proxy_r2,
            "tracking_error_60": tracking_error,
            "proxy_quality_flag": proxy_quality,
            "proxy_based_confidence": _proxy_confidence(proxy_r2, point_metrics),
            "proxy_features_helpful": proxy_features_helpful,
            "holding_report_date": proxy_meta.get("holding_report_date"),
            "holding_scope": proxy_meta.get("holding_scope", "unavailable"),
            "top10_proxy_available_count": proxy_meta.get("top10_proxy_available_count", 0),
            "top10_proxy_missing_count": proxy_meta.get("top10_proxy_missing_count", 0),
            "top10_proxy_status": proxy_meta.get("top10_proxy_status", "unavailable"),
            "failed_stock_codes": proxy_meta.get("failed_stock_codes", []),
            "stock_sources_used": proxy_meta.get("stock_sources_used", {}),
            "theme_available_count": proxy_meta.get("theme_available_count", 0),
            "failed_themes": proxy_meta.get("failed_themes", []),
            "top_exposures": exposure_summary.get("top_exposures", []),
            "holding_lookahead_risk": proxy_meta.get("holding_lookahead_risk", True),
            "top10_proxy_backtest_not_strict": proxy_meta.get("top10_proxy_backtest_not_strict", True),
            "proxy_disclaimer": "代理组合根据公开披露持仓、主题指数和历史收益拟合构建，不代表基金真实实时持仓。",
            "theme_proxy_disclaimer": "当前主题因子为宽基代理，解释力有限。" if proxy_meta.get("theme_available_count", 0) > 0 else None,
            "point_prediction_health": _point_health(point_metrics),
            "direction_health": _direction_health(direction_metrics, signal),
            # V2.6 相对收益信号
            "excess_signals": _build_excess_signals(metrics),
            "exposure_shift_flag": metrics.get("exposure_shift_flag", False),
            "exposure_shift_details": metrics.get("exposure_shift_details", {}),
            # V2.6 模型监控
            "model_monitoring": _load_model_monitoring(fund_code),
            "baseline": {
                "baseline_zero_rmse_bp": point_metrics.get("baseline_zero_rmse_bp"),
                "baseline_mean_rmse_bp": point_metrics.get("baseline_mean_rmse_bp"),
                "baseline_median_rmse_bp": point_metrics.get("baseline_median_rmse_bp"),
                "baseline_last_rmse_bp": point_metrics.get("baseline_last_rmse_bp"),
                "model_vs_zero_improvement": point_metrics.get("model_vs_zero_improvement"),
                "model_vs_mean_improvement": point_metrics.get("model_vs_mean_improvement"),
            },
            "metrics": metrics,
            "selected_feature_count": len(config.get("selected_features_point", [])),
            "stale": bool(meta.get("stale")),
            "request_id": request_id,
        }
        append_prediction(
            fund_code,
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "asof_date": result["asof_date"],
                "prediction_mode": PREDICTION_MODE,
                "pred_return": pred,
                "p_up": p_up,
                "p_down": p_down,
                "direction_signal": signal,
                "direction_strength": strength,
                "actual": None,
                "abs_error": None,
                "direction_correct": None,
                "strong_signal": bool(p_up is not None and (p_up >= 0.60 or p_up <= 0.40)),
                "covered_80": None,
                "covered_90": None,
                "point_model_name": config.get("point_model_name"),
                "direction_model_name": config.get("direction_model_name"),
                "interval_method": interval_config.get("interval_method"),
                "flat_prediction": point_metrics.get("flat_prediction"),
                "pred_real_std_ratio": point_metrics.get("pred_real_std_ratio"),
                "pred_real_corr": point_metrics.get("pred_real_corr"),
                "model_vs_mean_improvement": point_metrics.get("model_vs_mean_improvement"),
                "strong_signal_win_rate": direction_metrics.get("strong_signal_win_rate"),
                "residual_group_used": regime,
                "residual_group_fallback": fallback,
                "today_nav": today_nav,
                "pred_nav": pred_nav,
                "lower_nav_80": nav_interval_80["lower"],
                "upper_nav_80": nav_interval_80["upper"],
                "lower_nav_90": nav_interval_90["lower"],
                "upper_nav_90": nav_interval_90["upper"],
                "proxy_r2_60": proxy_r2,
                "tracking_error_60": tracking_error,
                "proxy_quality_flag": proxy_quality,
                "proxy_features_helpful": proxy_features_helpful,
                "holding_report_date": proxy_meta.get("holding_report_date"),
                "holding_scope": proxy_meta.get("holding_scope", "unavailable"),
                "top10_proxy_available_count": proxy_meta.get("top10_proxy_available_count", 0),
                "theme_available_count": proxy_meta.get("theme_available_count", 0),
                "lower_70": result["lower_70"],
                "upper_70": result["upper_70"],
                "lower_80": result["lower_80"],
                "upper_80": result["upper_80"],
                "lower_90": result["lower_90"],
                "upper_90": result["upper_90"],
                "lower_99": result["lower_99"],
                "upper_99": result["upper_99"],
            },
        )
        set_log_context(stage="predict_success")
        logger.info("predict_success asof=%s pred=%.8f p_up=%s", result["asof_date"], pred, p_up)
        return result
    except Exception:
        set_log_context(stage="predict_failed")
        logger.exception("predict_failed")
        raise


def _build_excess_signals(metrics: dict) -> dict:
    """构建相对收益信号 (V2.6)"""
    excess = metrics.get("excess", {})
    signals = {
        "outperform_cyb": None,
        "outperform_kcb50": None,
        "outperform_top10": None,
        "outperform_theme": None,
        "stronger_than_absolute": False,
        "reliable_count": 0,
    }
    
    reliable_models = 0
    
    for name, data in excess.items():
        if not data.get("model_available"):
            continue
        
        outperform_prob = data.get("outperform_prob", 0.5)
        corr = data.get("excess_corr", 0)
        auc = data.get("excess_auc")
        
        # 只有当相关性 > 0.1 且 AUC > 0.55 时才认为可靠
        is_reliable = corr > 0.1 and (auc is None or auc > 0.55)
        
        if name == "excess_cyb":
            signals["outperform_cyb"] = {
                "prob": outperform_prob,
                "direction": "outperform" if outperform_prob > 0.5 else "underperform",
                "reliable": is_reliable,
                "corr": corr,
                "auc": auc,
            }
        elif name == "excess_kcb50":
            signals["outperform_kcb50"] = {
                "prob": outperform_prob,
                "direction": "outperform" if outperform_prob > 0.5 else "underperform",
                "reliable": is_reliable,
                "corr": corr,
                "auc": auc,
            }
        elif name == "excess_top10":
            signals["outperform_top10"] = {
                "prob": outperform_prob,
                "direction": "outperform" if outperform_prob > 0.5 else "underperform",
                "reliable": is_reliable,
                "corr": corr,
                "auc": auc,
            }
        elif name == "excess_theme":
            signals["outperform_theme"] = {
                "prob": outperform_prob,
                "direction": "outperform" if outperform_prob > 0.5 else "underperform",
                "reliable": is_reliable,
                "corr": corr,
                "auc": auc,
            }
        
        if is_reliable:
            reliable_models += 1
    
    signals["reliable_count"] = reliable_models
    
    # 判断相对收益信号是否强于绝对收益信号
    point_corr = metrics.get("point", {}).get("pred_real_corr", 0)
    if reliable_models > 0:
        avg_excess_corr = float(np.mean([d.get("excess_corr", 0) for d in excess.values() if d.get("model_available")]))
        signals["stronger_than_absolute"] = bool(avg_excess_corr > point_corr + 0.05)
    
    return signals


def _load_model_monitoring(fund_code: str) -> dict:
    """加载模型监控记录 (V2.6)"""
    import json
    from pathlib import Path
    
    monitor_path = Path("models") / fund_code / "t_plus_1_close" / "model_monitoring.json"
    
    if monitor_path.exists():
        with open(monitor_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {"predictions": [], "degradation_flag": False}
