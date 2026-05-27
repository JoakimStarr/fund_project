"""
灵活配置型基金两阶段仓位估算。

策略方案 §5.4 实现：
- 阶段1：滚动Beta反推当前股票仓位
- 阶段2：动态加权偏股因子集和债券因子集
"""
import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def estimate_position_rolling_beta(
    df: pd.DataFrame,
    benchmark_col: str = "hs300_ret",
    window: int = 10,
) -> pd.Series:
    """用滚动beta系数反推当前股票仓位
    
    仓位 ≈ corr(基金收益, 基准收益) × std(基金) / std(基准)
    
    Args:
        df: 含基金和基准收益率的DataFrame
        benchmark_col: 基准列名
        window: 滚动窗口
    
    Returns:
        仓位估计序列
    """
    positions = np.full(len(df), np.nan)
    
    fund_col = "fund_ret"
    if fund_col not in df.columns or benchmark_col not in df.columns:
        return pd.Series(positions, index=df.index)
    
    for i in range(window, len(df)):
        w = df.iloc[i - window : i]
        fund_r = w[fund_col].dropna()
        bench_r = w[benchmark_col].reindex(fund_r.index).dropna()
        
        if len(fund_r) < 5 or len(bench_r) < 5:
            continue
        
        corr = fund_r.corr(bench_r)
        fund_std = fund_r.std()
        bench_std = bench_r.std() + 1e-8
        
        position = abs(corr) * fund_std / bench_std
        position = max(0.0, min(position, 1.05))  # 约束到合理范围
        positions[i] = position
    
    return pd.Series(positions, index=df.index)


def flexible_predict_two_stage(
    equity_pred: dict[str, Any],
    bond_pred: Optional[dict[str, Any]],
    estimated_position: float,
    fund_code: str,
) -> dict[str, Any]:
    """灵活配置两阶段动态加权预测
    
    Args:
        equity_pred: 偏股模型预测结果
        bond_pred: 债券模型预测结果（可为None）
        estimated_position: 当前估计仓位（0~1）
        fund_code: 基金代码
    
    Returns:
        加权预测结果
    """
    set_log_context(stage="flexible_two_stage_predict")
    logger.info(
        "flexible_predict fund_code=%s position=%.2f",
        fund_code, estimated_position,
    )
    
    eq_ret = equity_pred.get("pred_return", 0.0)
    eq_nav = equity_pred.get("today_nav", 1.0)
    
    if bond_pred is not None and estimated_position < 0.7:
        bd_ret = bond_pred.get("pred_return", 0.0)
        
        if estimated_position > 0.6:
            weight_eq = estimated_position
            weight_bd = 1 - estimated_position
        elif estimated_position > 0.3:
            weight_eq = 0.5
            weight_bd = 0.5
        else:
            weight_eq = estimated_position
            weight_bd = 1 - estimated_position
        
        blended_ret = weight_eq * eq_ret + weight_bd * bd_ret
        blended_nav = eq_nav * (1 + blended_ret)
        
        method = "blended_eb"
    else:
        blended_ret = eq_ret
        blended_nav = eq_nav * (1 + eq_ret)
        weight_eq = 1.0
        weight_bd = 0.0
        method = "equity_dominant"
    
    result = {
        **equity_pred,
        "fund_code": fund_code,
        "fund_type": "hybrid_flexible",
        "prediction_mode": method,
        "pred_return": blended_ret,
        "pred_nav": blended_nav,
        "estimated_position": round(estimated_position, 3),
        "equity_weight": round(weight_eq, 3),
        "bond_weight": round(weight_bd, 3),
        "position_regime": (
            "high_equity" if estimated_position > 0.6 else
            "balanced" if estimated_position > 0.3 else
            "high_bond"
        ),
        "fund_profile": {
            "type": "hybrid_flexible",
            "position_estimation": "rolling_beta",
        },
    }
    
    set_log_context(stage="flexible_predict_success")
    return result


def get_position_trend(
    df: pd.DataFrame,
    window: int = 20,
) -> dict[str, Any]:
    """分析仓位趋势方向
    
    用于判断基金经理是否正在调仓
    """
    positions = estimate_position_rolling_beta(df)
    
    if positions.dropna().empty:
        return {"trend": "unknown", "recent_mean": None, "trend_slope": None}
    
    recent = positions.dropna().iloc[-window:]
    mean_pos = recent.mean()
    
    if len(recent) >= 5:
        slope = np.polyfit(range(len(recent)), recent.values, 1)[0]
        trend = "increasing" if slope > 0.002 else "decreasing" if slope < -0.002 else "stable"
    else:
        slope = None
        trend = "unknown"
    
    return {
        "trend": trend,
        "recent_mean": round(float(mean_pos), 3),
        "trend_slope": round(float(slope), 5) if slope else None,
        "min_recent": round(float(recent.min()), 3),
        "max_recent": round(float(recent.max()), 3),
    }