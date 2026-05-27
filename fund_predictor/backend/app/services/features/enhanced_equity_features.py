"""
偏股类增强因子：宏观、情绪、日历效应等额外因子构建。

策略方案 §5.1 补充：
- 宏观因子（利率/CPI/PMI）
- 资金流向/情绪因子
- 日历效应因子
"""
import logging
import re
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import PROCESSED_DIR
from app.core.errors import AppError, DuplicateFeatureColumnsError, FeatureBuildError, InsufficientDataError
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)


def build_enhanced_equity_features(df: pd.DataFrame) -> pd.DataFrame:
    """在现有因子基础上添加增强因子
    
    注意：此函数不依赖外部API调用（akshare宏观数据），
    仅使用已有数据计算可派生的增强因子。外部宏观数据获取
    在后续版本中通过独立服务实现。
    """
    set_log_context(stage="enhanced_feature_build_start")
    logger.info("enhanced_feature_build_start")
    
    # === A. 市场情绪因子（从指数行情派生） ===
    
    # 涨跌比：当日上涨指数数量占比
    index_ret_cols = [c for c in df.columns if c.endswith("_ret") and any(idx in c for idx in ["hs300", "zz500", "zz1000", "cyb", "kcb50"])]
    if len(index_ret_cols) >= 3:
        up_count = sum(df[c] > 0 for c in index_ret_cols)
        down_count = sum(df[c] < 0 for c in index_ret_cols)
        df["market_up_ratio"] = up_count / len(index_ret_cols)
        df["market_down_ratio"] = down_count / len(index_ret_cols)
        df["market_adv_dec"] = df["market_up_ratio"] - df["market_down_ratio"]
        df["market_adv_dec_mean_5"] = df["market_adv_dec"].rolling(5).mean()
        df["market_adv_dec_mean_20"] = df["market_adv_dec"].rolling(20).mean()
    
    # 恐慌指数代理：市场波动率偏离度
    if "hs300_ret" in df.columns:
        vol_20 = df["hs300_ret"].rolling(20).std()
        vol_60 = df["hs300_ret"].rolling(60).std()
        df["vol_ratio_20_vs_60"] = vol_20 / (vol_60 + 1e-8)
        df["vol_spike_20"] = (vol_20 > vol_60 * 1.5).astype(int)
    
    # 创业板/科创板成交活跃度代理（波动率比）
    if "cyb_ret" in df.columns and "hs300_ret" in df.columns:
        cyb_vol = df["cyb_ret"].rolling(20).std()
        hs_vol = df["hs300_ret"].rolling(20).std()
        df["growth_style_activity"] = cyb_vol / (hs_vol + 1e-8)
        df["growth_style_activity_mean_5"] = df["growth_style_activity"].rolling(5).mean()
    
    # === B. 日历效应因子 ===
    
    dates = pd.to_datetime(df["date"])
    
    # 星期几哑变量（周一=0 ... 周五=4）
    df["weekday"] = dates.dt.weekday
    for wd in range(5):
        df[f"is_weekday_{wd}"] = (df["weekday"] == wd).astype(int)
    
    # 月初/月末效应
    day_of_month = dates.dt.day
    df["is_month_start"] = ((day_of_month <= 3)).astype(int)
    df["is_month_end"] = ((day_of_month >= 28)).astype(int)
    df["is_quarter_end"] = (dates.dt.month.isin([3, 6, 9, 12]) & (day_of_month >= 25)).astype(int)
    df["quarter_end_window"] = df["is_quarter_end"].rolling(10).sum()
    
    # 季报窗口（季末前后10个交易日）
    quarter_months = dates.dt.month.isin([3, 6, 9, 12])
    near_quarter_end = (quarter_months & (day_of_month >= 18))
    df["report_window"] = near_quarter_end.astype(int)
    df["report_window_sum_10"] = df["report_window"].rolling(10).sum()
    
    # 节前效应（简单近似：月末+季末叠加）
    df["holiday_proxy"] = df["is_month_end"] | df["is_quarter_end"]
    df["holiday_proxy_sum_5"] = df["holiday_proxy"].rolling(5).sum()
    
    # === C. 动量反转增强 ===
    
    if "fund_ret" in df.columns:
        # 短期反转信号
        df["reversal_signal"] = df["fund_ret_mom_5"] * (-1) * df["fund_ret_mom_20"]
        
        # 动量质量：近期动量是否持续（短期动量与中期动量同向）
        mom_sign_5 = np.sign(df["fund_ret_mom_5"])
        mom_sign_20 = np.sign(df["fund_ret_mom_20"])
        df["momentum_quality"] = (mom_sign_5 == mom_sign_20).astype(int)
        
        # 波动率状态切换
        vol_20 = df["fund_ret_std_20"]
        vol_60 = df["fund_ret_std_60"]
        df["vol_regime_change"] = ((vol_20 > vol_60 * 1.2) | (vol_20 < vol_60 * 0.8)).astype(int)
        df["vol_expanding"] = (vol_20 > vol_60 * 1.2).astype(int)
        df["vol_contracting"] = (vol_20 < vol_60 * 0.8).astype(int)
    
    # === D. 跨指数动量差异 ===
    
    if all(c in df.columns for c in ["cyb_mom_5", "hs300_mom_5"]):
        df["style_rotation_growth_value"] = df["cyb_mom_5"] - df["hs300_mom_5"]
        df["style_rotation_small_large"] = df.get("zz1000_mom_5", pd.Series(dtype=float)) - df["hs300_mom_5"]
    
    if all(c in df.columns for c in ["style_growth_vs_large", "style_small_vs_large"]):
        df["style_divergence"] = np.abs(df["style_growth_vs_large"]) + np.abs(df["style_small_vs_large"])
        df["style_divergence_mean_5"] = df["style_divergence"].rolling(5).mean()
    
    # === E. 极端行情标记 ===
    
    if "hs300_ret" in df.columns:
        extreme_up = df["hs300_ret"] > 0.03
        extreme_down = df["hs300_ret"] < -0.03
        df["extreme_market_day"] = (extreme_up | extreme_down).astype(int)
        df["extreme_up_day"] = extreme_up.astype(int)
        df["extreme_down_day"] = extreme_down.astype(int)
        df["extreme_day_count_5"] = df["extreme_market_day"].rolling(5).sum()
    
    # 清理临时中间列
    temp_cols = ["weekday"]
    df = df.drop(columns=[c for c in temp_cols if c in df.columns], errors="ignore")
    
    new_feature_count = len(model_feature_columns_from_df(df))
    set_log_context(stage="enhanced_feature_build_success")
    logger.info("enhanced_feature_build_success new_total_features=%d", new_feature_count)
    
    return df


def model_feature_columns_from_df(df: pd.DataFrame) -> list[str]:
    """从DataFrame中提取模型特征列（复用feature_service的逻辑但允许扩展）"""
    excluded_exact = {
        "date", "feature_date", "target_date",
        "target_next", "nav", "acc_nav"
    }
    banned_suffixes = ("_open", "_close", "_high", "_low", "_volume")
    banned_keywords = ("target", "next", "future", "label")
    
    feature_cols = []
    for c in df.columns:
        if c in excluded_exact:
            continue
        if c.endswith(banned_suffixes):
            continue
        col_lower = c.lower()
        if any(keyword in col_lower for keyword in banned_keywords):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if not df[c].notna().any():
            continue
        feature_cols.append(c)
    
    return feature_cols