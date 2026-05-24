"""
Conformal Prediction 保形预测置信区间模块。

策略方案 §9.1 实现：
- 无需对残差分布做任何假设
- 保证统计意义上的覆盖率
- 实现简单，适合生产环境
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.core.config import MODEL_DIR
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)


def conformal_interval(
    model,
    X_calib: pd.DataFrame,
    y_calib: np.ndarray | pd.Series,
    X_new: pd.DataFrame,
    alpha: float = 0.10,
    feature_cols: Optional[list[str]] = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """保形预测：生成 coverage 保证的预测区间
    
    方法：基于校准集的非一致性得分分位数法
    
    Args:
        model: 已训练的回归模型
        X_calib: 校准集特征
        y_calib: 校准集标签
        X_new: 新样本特征
        alpha: 显著水平（0.1 → 90%覆盖率）
        feature_cols: 特征列名列表
    
    Returns:
        (lower_bounds, upper_bounds, metadata)
    """
    set_log_context(stage="conformal_prediction_start")
    logger.info("conformal_prediction_start calib_size=%d new_size=%d alpha=%.2f", len(X_calib), len(X_new), alpha)
    
    if len(X_calib) < 20:
        logger.warning("conformal_prediction_fallback calib_size_too_small=%d", len(X_calib))
        pred_new = model.predict(X_new[feature_cols] if feature_cols else X_new)
        std_est = np.abs(pred_new) * 0.02
        return pred_new - 2*std_est, pred_new + 2*std_est, {
            "method": "fallback_std",
            "calib_size": len(X_calib),
            "alpha": alpha,
            "warning": "insufficient_calibration_data",
        }
    
    cols = feature_cols if feature_cols else [c for c in X_calib.columns if c in X_new.columns]
    
    calib_pred = model.predict(X_calib[cols])
    scores = np.abs(y_calib - calib_pred)
    
    threshold = np.quantile(scores, 1 - alpha)
    
    new_pred = model.predict(X_new[cols])
    lower = new_pred - threshold
    upper = new_pred + threshold
    
    meta = {
        "method": "conformal_quantile",
        "calib_size": int(len(X_calib)),
        "new_size": int(len(X_new)),
        "alpha": float(alpha),
        "expected_coverage": float(1 - alpha),
        "threshold": float(threshold),
        "threshold_bp": float(threshold * 10000),
        "mean_score": float(np.mean(scores)),
        "median_score": float(np.median(scores)),
        "interval_width": float(2 * threshold),
        "interval_width_bp": float(2 * threshold * 10000),
    }
    
    set_log_context(stage="conformal_prediction_success")
    logger.info(
        "conformal_prediction_success threshold=%.6f width_bp=%.1f",
        threshold, meta["interval_width_bp"],
    )
    
    return lower, upper, meta


def adaptive_conformal_interval(
    model,
    X_calib: pd.DataFrame,
    y_calib: np.ndarray | pd.Series,
    X_new: pd.DataFrame,
    base_alpha: float = 0.10,
    volatility_col: Optional[str] = None,
    feature_cols: Optional[list[str]] = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """自适应保形预测：根据当前波动率动态调整置信区间宽度
    
    高波动时期自动扩大区间，低波动时期收窄区间。
    """
    lower, upper, meta = conformal_interval(model, X_calib, y_calib, X_new, base_alpha, feature_cols)
    
    if volatility_col and volatility_col in X_new.columns:
        vol = X_new[volatility_col].fillna(1.0).to_numpy()
        vol_median = np.median(vol)
        adjustment = np.clip(vol / (vol_median + 1e-8), 0.7, 2.0)
        
        center = (lower + upper) / 2
        half_width = (upper - lower) / 2 * adjustment
        lower = center - half_width
        upper = center + half_width
        
        meta["method"] = "adaptive_conformal"
        meta["volatility_adjustment"] = {
            "col": volatility_col,
            "median_vol": float(vol_median),
            "mean_adjustment": float(np.mean(adjustment)),
        }
    
    return lower, upper, meta


def save_conformal_config(fund_code: str, config: dict[str, Any], prediction_mode: str = "t_plus_1_close"):
    """保存保形预测配置到模型目录"""
    config_path = MODEL_DIR / fund_code / prediction_mode / "conformal_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info("conformal_config_saved fund_code=%s path=%s", fund_code, config_path)


def load_conformal_config(fund_code: str, prediction_mode: str = "t_plus_1_close") -> dict[str, Any]:
    """加载保形预测配置"""
    config_path = MODEL_DIR / fund_code / prediction_mode / "conformal_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}