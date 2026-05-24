import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_macro_cache = {}
_macro_cache_expiry = None
CACHE_TTL_HOURS = 6


def _fetch_bond_10y_rate() -> pd.DataFrame:
    """获取10年期国债收益率"""
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        if df is not None and not df.empty:
            df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "rate_10y"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["rate_10y"] = pd.to_numeric(df["rate_10y"], errors="coerce")
            return df[["date", "rate_10y"]].dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取10年期国债收益率失败: %s", e)
    return pd.DataFrame(columns=["date", "rate_10y"])


def _fetch_cpi_data() -> pd.DataFrame:
    """获取CPI同比数据"""
    try:
        import akshare as ak
        df = ak.macro_china_cpi_yearly()
        if df is not None and not df.empty:
            col_map = {str(c).strip(): c for c in df.columns}
            date_col = next((c for c in ["月份", "日期", "date"] if c in col_map), None)
            val_col = next((c for c in ["全国当月同比(%)", "cpi", "CPI"] if c in col_map), None)
            if date_col and val_col:
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "cpi_yoy": pd.to_numeric(df[val_col], errors="coerce") / 100.0,
                })
                return out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取CPI数据失败: %s", e)
    return pd.DataFrame(columns=["date", "cpi_yoy"])


def _fetch_pmi_data() -> pd.DataFrame:
    """获取PMI数据"""
    try:
        import akshare as ak
        df = ak.macro_china_pmi()
        if df is not None and not df.empty:
            col_map = {str(c).strip(): c for c in df.columns}
            date_col = next((c for c in ["月份", "日期", "date"] if c in col_map), None)
            val_col = next((c for c in ["制造业PMI", "pmi", "PMI"] if c in col_map), None)
            if date_col and val_col:
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "pmi_value": pd.to_numeric(df[val_col], errors="coerce"),
                })
                return out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取PMI数据失败: %s", e)
    return pd.DataFrame(columns=["date", "pmi_value"])


def _fetch_m2_growth() -> pd.DataFrame:
    """获取M2货币供应量增速（社融相关）"""
    try:
        import akshare as ak
        df = ak.macro_china_money_supply()
        if df is not None and not df.empty:
            col_map = {str(c).strip(): c for c in df.columns}
            date_col = next((c for c in ["月份", "日期", "date"] if c in col_map), None)
            val_col = next((c for c in ["M2同比增长(%)", "M2货币供应同比"] if c in col_map), None)
            if date_col and val_col:
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "m2_growth": pd.to_numeric(df[val_col], errors="coerce") / 100.0,
                })
                return out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取M2增速数据失败: %s", e)
    return pd.DataFrame(columns=["date", "m2_growth"])


def _fetch_north_flow() -> pd.DataFrame:
    """获取北向资金净流入数据"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            col_map = {str(c).strip(): c for c in df.columns}
            date_col = next((c for c in ["date", "日期"] if c in col_map), None)
            flow_cols = [c for c in col_map if "净流入" in c or "flow" in c.lower()]
            val_col = flow_cols[0] if flow_cols else None
            if date_col and val_col:
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "north_flow": pd.to_numeric(df[val_col], errors="coerce") * 1e-4,
                })
                return out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取北向资金数据失败: %s", e)
    return pd.DataFrame(columns=["date", "north_flow"])


def _fetch_dr007() -> pd.DataFrame:
    """获取DR007银行间利率"""
    try:
        import akshare as ak
        df = ak.macro_china_shibor_all()
        if df is not None and not df.empty:
            col_map = {str(c).strip(): c for c in df.columns}
            date_col = next((c for c in ["date", "日期"] if c in col_map), None)
            dr_col = next((c for c in col_map if "DR007" in c or "dr007" in c.lower()), None)
            if date_col and dr_col:
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "dr007_level": pd.to_numeric(df[dr_col], errors="coerce") / 100.0,
                })
                return out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    except Exception as e:
        logger.warning("获取DR007数据失败: %s", e)
    return pd.DataFrame(columns=["date", "dr007_level"])


def _load_all_macro_data() -> dict[str, pd.DataFrame]:
    """加载所有宏观数据源，返回字典"""
    fetchers = {
        "bond": _fetch_bond_10y_rate,
        "cpi": _fetch_cpi_data,
        "pmi": _fetch_pmi_data,
        "m2": _fetch_m2_growth,
        "north": _fetch_north_flow,
        "dr007": _fetch_dr007,
    }
    result = {}
    for name, fn in fetchers.items():
        try:
            data = fn()
            result[name] = data
            logger.info("macro_fetch_success source=%s rows=%s", name, len(data))
        except Exception as e:
            logger.warning("macro_fetch_failed source=%s error=%s", name, e)
            result[name] = pd.DataFrame()
    return result


def build_macro_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    在现有DataFrame基础上添加宏观因子特征列。

    从akshare获取：10年期国债收益率、CPI、PMI、社融(M2)、北向资金、DR007。
    构建特征列：rate_10y_chg, cpi_yoy, pmi_value, m2_growth, north_flow, dr007_level 等。

    如果akshare不可用则返回原始df不报错。

    Args:
        df: 原始特征DataFrame，必须包含'date'列

    Returns:
        添加了宏观特征列的DataFrame
    """
    global _macro_cache, _macro_cache_expiry

    set_log_context(stage="macro_feature_build_start")
    logger.info("macro_feature_build_start input_rows=%s", len(df))

    if df.empty or "date" not in df.columns:
        logger.warning("macro_feature_skip empty_or_no_date")
        return df.copy()

    now = datetime.now()
    if _macro_cache and _macro_cache_expiry and now < _macro_cache_expiry:
        macro_data = _macro_cache
        logger.info("macro_use_cached_data")
    else:
        try:
            import akshare as ak
            macro_data = _load_all_macro_data()
            _macro_cache = macro_data
            _macro_cache_expiry = now + timedelta(hours=CACHE_TTL_HOURS)
            logger.info("macro_fetched_fresh cache_ttl=%sh", CACHE_TTL_HOURS)
        except ImportError:
            logger.warning("macro_akshare_not_available returning_original_df")
            return df.copy()

    out = df.copy()
    dates = pd.to_datetime(out["date"], errors="coerce")

    bond_df = macro_data.get("bond", pd.DataFrame())
    if not bond_df.empty and "rate_10y" in bond_df.columns:
        merged = out[["date"]].merge(bond_df, on="date", how="left")
        out["rate_10y_level"] = merged["rate_10y"].values
        out["rate_10y_chg"] = out["rate_10y_level"].pct_change(5)
        out["rate_10y_ma20"] = out["rate_10y_level"].rolling(20).mean()

    cpi_df = macro_data.get("cpi", pd.DataFrame())
    if not cpi_df.empty and "cpi_yoy" in cpi_df.columns:
        merged = out[["date"]].merge(cpi_df, on="date", how="left")
        out["cpi_yoy"] = merged["cpi_yoy"].values
        out["cpi_yoy_ma3"] = out["cpi_yoy"].rolling(3, min_periods=1).mean()

    pmi_df = macro_data.get("pmi", pd.DataFrame())
    if not pmi_df.empty and "pmi_value" in pmi_df.columns:
        merged = out[["date"]].merge(pmi_df, on="date", how="left")
        out["pmi_value"] = merged["pmi_value"].values
        out["pmi_above_50"] = (out["pmi_value"] > 50).astype(int)

    m2_df = macro_data.get("m2", pd.DataFrame())
    if not m2_df.empty and "m2_growth" in m2_df.columns:
        merged = out[["date"]].merge(m2_df, on="date", how="left")
        out["m2_growth"] = merged["m2_growth"].values
        out["m2_growth_chg"] = out["m2_growth"].diff(1)

    north_df = macro_data.get("north", pd.DataFrame())
    if not north_df.empty and "north_flow" in north_df.columns:
        merged = out[["date"]].merge(north_df, on="date", how="left")
        out["north_flow"] = merged["north_flow"].values
        out["north_flow_ma5"] = out["north_flow"].rolling(5).mean()
        out["north_flow_cum20"] = out["north_flow"].rolling(20).sum()

    dr007_df = macro_data.get("dr007", pd.DataFrame())
    if not dr007_df.empty and "dr007_level" in dr007_df.columns:
        merged = out[["date"]].merge(dr007_df, on="date", how="left")
        out["dr007_level"] = merged["dr007_level"].values
        out["dr007_ma5"] = out["dr007_level"].rolling(5).mean()
        out["dr007_vol20"] = out["dr007_level"].rolling(20).std()

    out = out.replace([np.inf, -np.inf], np.nan)

    new_macro_cols = [
        c for c in out.columns
        if c.startswith(("rate_10y_", "cpi_", "pmi_", "m2_", "north_", "dr007_"))
        and c not in df.columns
    ]
    set_log_context(stage="macro_feature_build_success")
    logger.info(
        "macro_feature_build_success new_columns=%s total_rows=%s",
        new_macro_cols,
        len(out),
    )
    return out
