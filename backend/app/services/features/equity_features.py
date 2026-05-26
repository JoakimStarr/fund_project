import numpy as np
import pandas as pd


def calc_style_exposure(fund_returns: pd.Series, growth_returns: pd.Series, value_returns: pd.Series, window: int = 60) -> float:
    common = fund_returns.dropna().index.intersection(growth_returns.dropna().index).intersection(value_returns.dropna().index)
    if len(common) < window:
        return np.nan
    fr = fund_returns.loc[common]
    gr = growth_returns.loc[common]
    vr = value_returns.loc[common]
    g_corr = fr.rolling(window).corr(gr)
    v_corr = fr.rolling(window).corr(vr)
    return g_corr.iloc[-1] - v_corr.iloc[-1] if not g_corr.empty else np.nan


def calc_holding_weighted_return(holdings: pd.DataFrame, stock_returns: dict) -> float:
    total = 0.0
    for _, h in holdings.iterrows():
        weight = float(h.get("weight", 0) if pd.notna(h.get("weight")) else 0)
        ret = stock_returns.get(str(h.get("stock_code", "")).strip(), 0)
        total += weight * ret
    return total