"""
指数/ETF 规则引擎：规则优先 + ML校正。

策略方案 §5.3 实现：
- 核心公式：T+1 净值 ≈ T日净值 × (1 + 标的指数涨跌幅 × 跟踪倍率 - 日管理费)
- ML模型仅用于修正跟踪误差
"""
import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DAILY_FEE = 0.000003  # 约0.0003%/日管理费


def predict_index_fund(
    fund_code: str,
    today_nav: float,
    index_symbol: str,
    index_data: pd.DataFrame,
    ml_correction_model=None,
    feature_cols: Optional[list] = None,
    latest_features: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """指数基金规则预测
    
    Args:
        fund_code: 基金代码
        today_nav: T日净值
        index_symbol: 标的指数代码（如 sh000300）
        index_data: 指数历史行情DataFrame
        ml_correction_model: ML校正模型（可选）
        feature_cols: ML特征列名
        latest_features: 最新特征行
    
    Returns:
        预测结果字典
    """
    set_log_context(stage="index_rule_prediction_start")
    logger.info("index_rule_prediction_start fund_code=%s index=%s", fund_code, index_symbol)
    
    if index_data.empty or len(index_data) < 2:
        raise ValueError(f"Index data insufficient for {index_symbol}")
    
    # 获取最近一个交易日的指数收益率作为T+1预期
    last_index_ret = index_data.iloc[-1]["close"] / index_data.iloc[-2]["close"] - 1
    
    # 规则预测
    rule_pred_return = last_index_ret * 1.0 - DAILY_FEE  # 跟踪倍率=1（非杠杆ETF）
    rule_pred_nav = today_nav * (1 + rule_pred_return)
    
    result = {
        "fund_code": fund_code,
        "fund_type": "index_equity",
        "prediction_mode": "rule_primary",
        "asof_date": str(pd.to_datetime(index_data.iloc[-1]["date"]).date()),
        "today_nav": today_nav,
        "pred_return": rule_pred_return,
        "pred_nav": rule_pred_nav,
        "index_symbol": index_symbol,
        "index_last_return": last_index_ret,
        "tracking_multiplier": 1.0,
        "daily_fee": DAILY_FEE,
        "rule_pred_return": rule_pred_return,
        "rule_pred_nav": rule_pred_nav,
        "ml_corrected": False,
        "ml_correction": 0.0,
        "fund_profile": {
            "type": "index_equity",
            "prediction_method": "rule_engine",
        },
    }
    
    # ML校正层
    if ml_correction_model is not None and latest_features is not None and feature_cols is not None:
        try:
            aligned = latest_features[[c for c in feature_cols if c in latest_features.columns]].fillna(0.0)
            correction = float(ml_correction_model.predict(aligned)[0])
            
            final_return = rule_pred_return + correction
            final_nav = today_nav * (1 + final_return)
            
            result["pred_return"] = final_return
            result["pred_nav"] = final_nav
            result["ml_correction"] = correction
            result["ml_corrected"] = True
            result["prediction_mode"] = "rule_plus_ml"
            logger.info(
                "index_ml_correction applied fund_code=%s correction=%.6f",
                fund_code, correction,
            )
        except Exception as exc:
            logger.warning("index_ml_correction_failed fund_code=%s error=%s", fund_code, exc)
    
    # 区间估算（基于指数历史波动率）
    if len(index_data) >= 60:
        index_vol = index_data["close"].pct_change().dropna().iloc[-20:].std()
        interval_width = index_vol * 2.0  # 约2倍标准差
        
        result["nav_interval_80"] = {
            "lower": max(0, result["pred_nav"] * (1 - interval_width)),
            "upper": result["pred_nav"] * (1 + interval_width),
            "width_bp": interval_width * 2 * 10000,
        }
        result["interval_method"] = "index_volatility_rule"
    
    set_log_context(stage="index_rule_prediction_success")
    logger.info("index_rule_prediction_success fund_code=%s", fund_code)
    
    return result