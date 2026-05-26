import numpy as np
import pandas as pd


def calc_momentum(df: pd.DataFrame, windows: list = None) -> dict:
    if windows is None:
        windows = [1, 2, 3, 5, 10, 20, 60]
    result = {}
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    for w in windows:
        result[f"ret_{w}d"] = nav.pct_change(w)
    return result


def calc_volatility(df: pd.DataFrame, windows: list = None) -> dict:
    if windows is None:
        windows = [5, 10, 20, 60]
    result = {}
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    returns = nav.pct_change()
    for w in windows:
        vol = returns.rolling(w).std() * np.sqrt(252)
        result[f"vol_{w}d"] = vol
    return result


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(series: pd.Series) -> pd.Series:
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    return hist


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    nav = df["nav"] if "nav" in df.columns else df.iloc[:, 0]
    idx = df.index if hasattr(df, 'index') and isinstance(df.index, pd.DatetimeIndex) else range(len(df))
    all_series = {}
    for w in [1, 2, 3, 5, 10, 20, 60]:
        all_series[f"ret_{w}d"] = nav.pct_change(w)
    for w in [5, 10, 20, 60]:
        ret = nav.pct_change()
        all_series[f"vol_{w}d"] = ret.rolling(w).std() * np.sqrt(252)
    all_series["rsi_14"] = calc_rsi(nav)
    all_series["macd_hist"] = calc_macd(nav)
    feature_df = pd.DataFrame(all_series, index=idx)
    feature_df = feature_df.replace([float("inf"), float("-inf")], float("nan"))
    return feature_df