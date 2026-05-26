import numpy as np
import pandas as pd


def calc_north_flow_impact(north_flow_data: pd.DataFrame) -> dict:
    if north_flow_data is None or north_flow_data.empty:
        return {"north_net_flow": np.nan, "north_flow_ma5": np.nan}
    val_col = None
    for c in north_flow_data.columns:
        if "net" in c.lower() or "flow" in c.lower() or "value" in c.lower():
            val_col = c
            break
    if val_col is None:
        val_col = north_flow_data.columns[0]
    values = north_flow_data[val_col].dropna().astype(float)
    if values.empty:
        return {"north_net_flow": np.nan, "north_flow_ma5": np.nan}
    return {
        "north_net_flow": values.iloc[-1],
        "north_flow_ma5": values.tail(5).mean() if len(values) >= 5 else np.nan,
    }


def calc_exchange_rate_impact(usd_cny_data: pd.DataFrame) -> dict:
    if usd_cny_data is None or usd_cny_data.empty:
        return {"usd_cny": np.nan, "usd_cny_chg": np.nan}
    val_col = usd_cny_data.columns[0]
    values = usd_cny_data[val_col].dropna().astype(float)
    if values.empty:
        return {"usd_cny": np.nan, "usd_cny_chg": np.nan}
    return {
        "usd_cny": values.iloc[-1],
        "usd_cny_chg": values.pct_change().iloc[-1] if len(values) > 1 else np.nan,
    }


def calc_shibor_impact(shibor_data: pd.DataFrame) -> dict:
    if shibor_data is None or shibor_data.empty:
        return {"shibor_on": np.nan, "shibor_chg": np.nan}
    val_col = shibor_data.columns[0]
    values = shibor_data[val_col].dropna().astype(float)
    if values.empty:
        return {"shibor_on": np.nan, "shibor_chg": np.nan}
    return {
        "shibor_on": values.iloc[-1],
        "shibor_chg": values.diff().iloc[-1] if len(values) > 1 else np.nan,
    }