import numpy as np
import pandas as pd


def calc_momentum(df: pd.DataFrame, windows: list = None) -> dict:
    if windows is None:
        windows = [1, 2, 3, 5, 10, 20, 60]
    result = {}
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    for w in windows:
        result[f"ret_{w}d"] = nav.pct_change(w).iloc[-1] if len(nav) > w else np.nan
    return result


def calc_volatility(df: pd.DataFrame, windows: list = None) -> dict:
    if windows is None:
        windows = [5, 10, 20, 60]
    result = {}
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    returns = nav.pct_change()
    for w in windows:
        vol = returns.rolling(w).std().iloc[-1] if len(returns) > w else np.nan
        result[f"vol_{w}d"] = vol * np.sqrt(252) if vol is not None and not (isinstance(vol, float) and np.isnan(vol)) else np.nan
    return result


def calc_rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return np.nan
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else np.nan


def calc_macd(series: pd.Series) -> float:
    if len(series) < 26:
        return np.nan
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    return hist.iloc[-1] if not hist.empty else np.nan


def compute_all(df: pd.DataFrame) -> dict:
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    result = {}
    result.update(calc_momentum(df))
    result.update(calc_volatility(df))
    result["rsi_14"] = calc_rsi(nav)
    result["macd_hist"] = calc_macd(nav)
    return result