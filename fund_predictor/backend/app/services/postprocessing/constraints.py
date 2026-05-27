"""
预测值约束规则模块：按基金类型约束预测值在合理范围内。

策略方案 §9.2 实现：
- 偏股混合/主动股票: ±20%
- 纯债: ±5%
- 可转债: ±20%
- 指数ETF: 跟随标的指数+涨跌停
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConstraintResult:
    """约束结果"""
    constrained_return: float
    original_return: float
    lower_limit: float
    upper_limit: float
    is_clipped: bool
    confidence_adjustment: str  # "normal" / "low"
    fund_type: str


NAV_LIMITS = {
    "hybrid_equity": 0.20,
    "equity_active": 0.20,
    "hybrid_balanced": 0.15,
    "hybrid_bond": 0.10,
    "hybrid_flexible": 0.20,
    "bond_pure": 0.05,
    "bond_mixed": 0.08,
    "bond_convertible": 0.20,
    "index_equity": None,  # 跟随标的指数，不在此处约束
    "index_bond": None,
    "fof": 0.15,
    "qdii": 0.20,
}


def apply_nav_constraints(
    pred_return: float,
    fund_type: str,
    today_nav: Optional[float] = None,
) -> ConstraintResult:
    """按基金类型约束日收益率预测值
    
    Args:
        pred_return: 预测的日收益率（小数形式）
        fund_type: 基金分类标签
        today_nav: 当日净值（用于计算净值级约束）
    
    Returns:
        ConstraintResult 包含约束后的值和元信息
    """
    limit = NAV_LIMITS.get(fund_type)
    
    if limit is None:
        return ConstraintResult(
            constrained_return=pred_return,
            original_return=pred_return,
            lower_limit=float("-inf"),
            upper_limit=float("inf"),
            is_clipped=False,
            confidence_adjustment="normal",
            fund_type=fund_type,
        )
    
    lower = -limit
    upper = limit
    
    if pred_return < lower:
        clipped = lower
        is_clipped = True
        adj = "low"
    elif pred_return > upper:
        clipped = upper
        is_clipped = True
        adj = "low"
    else:
        clipped = pred_return
        is_clipped = False
        adj = "normal"
    
    if is_clipped:
        logger.info(
            "nav_constraint_applied fund_type=%s original=%.4f constrained=%.4f limit=%.2f",
            fund_type, pred_return, clipped, limit,
        )
    
    return ConstraintResult(
        constrained_return=clipped,
        original_return=pred_return,
        lower_limit=lower,
        upper_limit=upper,
        is_clipped=is_clipped,
        confidence_adjustment=adj,
        fund_type=fund_type,
    )


def adjust_confidence_for_special_periods(
    asof_date_str: str,
    fund_profile: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """特殊时期置信度调整
    
    返回需要降低置信度的原因列表。
    
    策略方案 §9.3：
    - 季报披露窗口（前后10日）
    - 重大政策发布日
    - 极端波动日（前日涨跌 > ±3%）
    - 长假前后（3个交易日）
    - 基金经理变更后3个月内
    """
    from datetime import datetime
    
    adjustments = []
    
    try:
        asof_date = datetime.strptime(asof_date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return []
    
    # 季报窗口：3/6/9/12月末前后10个交易日
    month = asof_date.month
    day = asof_date.day
    if month in [3, 6, 9, 12] and 18 <= day <= 31:
        adjustments.append({
            "type": "report_window",
            "reason": "季报披露窗口，持仓数据即将更新",
            "confidence_penalty": -0.15,
        })
    
    # 月末效应
    if day >= 28:
        adjustments.append({
            "type": "month_end",
            "reason": "月末效应窗口",
            "confidence_penalty": -0.05,
        })
    
    # 年末效应（12月）
    if month == 12 and day >= 20:
        adjustments.append({
            "type": "year_end",
            "reason": "年末结算窗口",
            "confidence_penalty": -0.10,
        })
    
    # 基金经理变更检查
    if fund_profile:
        manager_change_days = fund_profile.get("manager_change_days")
        if manager_change_days is not None and manager_change_days < 90:
            adjustments.append({
                "type": "manager_change",
                "reason": f"基金经理变更后{manager_change_days}天，风格可能变化",
                "confidence_penalty": -0.25,
            })
    
    total_penalty = sum(a["confidence_penalty"] for a in adjustments)
    if total_penalty < -0.40:
        total_penalty = -0.40
    
    for a in adjustments:
        a["total_penalty"] = round(total_penalty, 3)
    
    return adjustments