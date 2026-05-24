"""
债券类因子构建模块：物理先验 + ML残差修正。

策略方案 §5.2 实现：
- 利率曲线因子（10Y/1Y/2Y收益率变动）
- 物理先验特征：-久期 × Δy
- 信用利差因子
- 流动性因子（DR007/Shibor）
- 可转债专项因子
"""
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import RAW_DIR

logger = logging.getLogger(__name__)

# 债券类型默认久期估算（当无法获取真实久期时）
DURATION_ESTIMATE = {
    "bond_pure": 3.0,
    "bond_mixed": 2.5,
    "bond_convertible": 1.5,
}


def build_bond_features(df: pd.DataFrame, fund_type: str = "bond_pure") -> tuple[pd.DataFrame, dict]:
    """构建债券型基金的专用特征
    
    Args:
        df: 已包含基础特征的DataFrame（来自build_features）
        fund_type: 债券子类型 bond_pure/bond_mixed/bond_convertible
    
    Returns:
        (df_with_bond_features, meta_dict)
    """
    set_log_context(stage="bond_feature_build_start")
    logger.info("bond_feature_build_start fund_type=%s", fund_type)
    
    duration = DURATION_ESTIMATE.get(fund_type, 2.5)
    meta = {"duration_estimate": duration, "fund_type": fund_type}
    
    # 尝试加载国债收益率数据
    bond_yields = _load_bond_yield_data()
    
    if bond_yields is not None and len(bond_yields) > 30:
        df = df.merge(bond_yields[["date", "yield_10y", "yield_1y", "yield_2y"]], on="date", how="left")
        
        # 利率曲线因子
        df["rate_10y_chg"] = df["yield_10y"].diff()
        df["rate_1y_chg"] = df["yield_1y"].diff()
        df["rate_2y_chg"] = df["yield_2y"].diff()
        
        # 期限利差
        df["term_spread_10y_2y"] = df["yield_10y"] - df["yield_2y"]
        df["term_spread_10y_1y"] = df["yield_10y"] - df["yield_1y"]
        df["term_spread_2y_1y"] = df["yield_2y"] - df["yield_1y"]
        
        # 曲线斜率变化
        df["curve_slope_chg"] = df["term_spread_10y_2y"].diff()
        df["curve_flattening"] = (df["term_spread_10y_2y"] < df["term_spread_10y_2y"].rolling(20).mean()).astype(int)
        
        # 核心物理先验特征：-久期 × Δ10Y国债收益率
        df["physics_prior_return"] = -duration * df["rate_10y_chg"]
        df["physics_prior_abs"] = np.abs(df["physics_prior_return"])
        
        # 滚动物理先验
        for win in [5, 10, 20]:
            df[f"physics_prior_mean_{win}"] = df["physics_prior_return"].rolling(win).mean()
            df[f"physics_prior_std_{win}"] = df["physics_prior_return"].rolling(win).std()
        
        meta["bond_data_available"] = True
        meta["bond_data_rows"] = len(bond_yields)
        logger.info("bond_yield_data_loaded rows=%d", len(bond_yields))
    else:
        # 无外部利率数据时，用市场指数作为替代信号
        logger.warning("bond_yield_data_unavailable using_index_proxies")
        
        if "hs300_ret" in df.columns:
            # 股债跷跷板效应：股市大跌时债市通常上涨
            df["stock_bond_seesaw"] = -df["hs300_ret"]
            df["stock_bond_seesaw_mean_5"] = df["stock_bond_seesaw"].rolling(5).mean()
        
        # 用固定久期估算物理先验（无实际利率变动时为零）
        df["physics_prior_return"] = 0.0
        df["physics_prior_abs"] = 0.0
        meta["bond_data_available"] = False
    
    # 流动性因子（DR007代理）
    liquidity = _load_liquidity_data()
    if liquidity is not None:
        df = df.merge(liquidity[["date", "dr007", "dr007_chg"]], on="date", how="left")
        
        if "dr007" in df.columns:
            df["dr007_mean_5"] = df["dr007"].rolling(5).mean()
            df["dr007_zscore_20"] = (df["dr007"] - df["dr007"].rolling(20).mean()) / (df["dr007"].rolling(20).std() + 1e-8)
            
            # DR007 vs 政策利率偏离（简化版：用历史均值作为政策利率代理）
            dr_policy = df["dr007"].rolling(120).mean()
            df["dr_deviation_policy"] = df["dr007"] - dr_policy
            df["tight_liquidity"] = (df["dr_deviation_policy"] > 0).astype(int)
        
        meta["liquidity_available"] = True
    else:
        meta["liquidity_available"] = False
    
    # 可转债专项因子
    if fund_type == "bond_convertible":
        df = _add_convertible_features(df)
        meta["convertible_specific"] = True
    
    # 信用利差代理（用风格因子中的成长vs大盘替代）
    if "style_growth_vs_large" in df.columns:
        df["credit_spread_proxy"] = df["style_growth_vs_large"].rolling(20).std()
        df["credit_spread_widening"] = (df["credit_spread_proxy"] > df["credit_spread_proxy"].rolling(60).mean()).astype(int)
    
    set_log_context(stage="bond_feature_build_success")
    logger.info("bond_feature_build_success fund_type=%s", fund_type)
    
    return df, meta


def _load_bond_yield_data() -> Optional[pd.DataFrame]:
    """尝试加载国债收益率数据"""
    path = RAW_DIR / "index" / "bond_10y.csv"
    path_1y = RAW_DIR / "index" / "bond_1y.csv"
    path_2y = RAW_DIR / "index" / "bond_2y.csv"
    
    dfs = {}
    for p, name in [(path, "10y"), (path_1y, "1y"), (path_2y, "2y")]:
        if p.exists():
            try:
                tmp = pd.read_csv(p, parse_dates=["date"])
                if "close" in tmp.columns:
                    dfs[name] = tmp[["date", "close"]].rename(columns={"close": f"yield_{name}"})
            except Exception:
                pass
    
    if len(dfs) == 0:
        return None
    
    result = list(dfs.values())[0]
    for d in list(dfs.values())[1:]:
        result = result.merge(d, on="date", how="outer")
    
    return result.sort_values("date").reset_index(drop=True)


def _load_liquidity_data() -> Optional[pd.DataFrame]:
    """尝试加载流动性数据（DR007）"""
    path = RAW_DIR / "index" / "dr007.csv"
    if path.exists():
        try:
            df = pd.read_csv(path, parse_dates=["date"])
            if "close" in df.columns:
                df["dr007"] = df["close"] / 100.0
                df["dr007_chg"] = df["dr007"].diff()
                return df[["date", "dr007", "dr007_chg"]]
        except Exception:
            pass
    return None


def _add_convertible_features(df: pd.DataFrame) -> pd.DataFrame:
    """添加可转债专项因子"""
    # 可转债兼具股性和债性，其收益受正股影响大
    if "hs300_ret" in df.columns:
        # 正股价值变动代理（沪深300代表整体权益市场）
        df["cb_equity_component"] = df["hs300_ret"]
        df["cb_equity_component_mean_5"] = df["cb_equity_component"].rolling(5).mean()
    
    # 波动率敏感度（转债有凸性，高波动时可能受益）
    if "hs300_ret_std_20" in df.columns or "fund_ret_std_20" in df.columns:
        vol_col = "hs300_ret_std_20" if "hs300_ret_std_20" in df.columns else "fund_ret_std_20"
        df["cb_convexity_proxy"] = df[vol_col]
        df["cb_high_vol_beneficiary"] = (df[vol_col] > df[vol_col].rolling(60).mean()).astype(int)
    
    # 转股溢价率代理（无法直接获取时用隐含波动率替代）
    if "vol_ratio_20_vs_60" in df.columns:
        df["cb_implied_volatility_proxy"] = df["vol_ratio_20_vs_60"]
    
    return df