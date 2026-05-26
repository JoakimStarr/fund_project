import numpy as np
import pandas as pd


def calc_beta(fund_returns: pd.Series, benchmark_returns: pd.Series, window: int = 20) -> float:
    common = fund_returns.dropna().index.intersection(benchmark_returns.dropna().index)
    if len(common) < window:
        return np.nan
    fr = fund_returns.loc[common]
    br = benchmark_returns.loc[common]
    cov = fr.rolling(window).cov(br)
    var = br.rolling(window).var()
    beta = cov / var.replace(0, np.nan)
    return beta.iloc[-1] if not beta.empty else np.nan


def calc_tracking_error(fund_returns: pd.Series, benchmark_returns: pd.Series, window: int = 20) -> float:
    common = fund_returns.dropna().index.intersection(benchmark_returns.dropna().index)
    if len(common) < window:
        return np.nan
    fr = fund_returns.loc[common]
    br = benchmark_returns.loc[common]
    te = (fr - br).rolling(window).std()
    return te.iloc[-1] if not te.empty else np.nan


def calc_alpha(fund_returns: pd.Series, benchmark_returns: pd.Series, risk_free: float = 0.0, window: int = 20) -> float:
    common = fund_returns.dropna().index.intersection(benchmark_returns.dropna().index)
    if len(common) < window:
        return np.nan
    fr = fund_returns.loc[common]
    br = benchmark_returns.loc[common]
    beta_series = fr.rolling(window).cov(br) / br.rolling(window).var().replace(0, np.nan)
    alpha = fr - risk_free - beta_series * (br - risk_free)
    return alpha.iloc[-1] if not alpha.empty else np.nan