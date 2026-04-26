import logging

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge

from backend.app.core.config import RAW_DIR
from backend.app.core.errors import DuplicateFeatureColumnsError, ProxyPortfolioError
from backend.app.core.logging_config import set_log_context
from backend.app.services.data_service import get_index_daily
from backend.app.services.holding_service import get_fund_holdings
from backend.app.services.stock_price_service import get_stock_daily_multi_source

logger = logging.getLogger(__name__)

THEME_PROXIES = {
    "semiconductor": ("index", "sh000688", "科创50代理"),
    "communication": ("index", "sz399006", "创业板代理"),
    "electronics": ("index", "sh000688", "科创50代理"),
    "computer": ("index", "sz399006", "创业板代理"),
    "ai": ("index", "sh000688", "科创50代理"),
    "cpo": ("index", "sz399006", "创业板代理"),
    "cloud_computing": ("index", "sz399006", "创业板代理"),
    "cybersecurity": ("index", "sz399006", "创业板代理"),
    "media": ("index", "sz399006", "创业板代理"),
    "cyb_growth": ("index", "sz399006", "创业板指"),
    "sse_star": ("index", "sh000688", "科创50"),
    "small_growth": ("index", "sh000852", "中证1000"),
}


def _compound_ret(s: pd.Series, window: int) -> pd.Series:
    return (1 + s).rolling(window).apply(np.prod, raw=True) - 1


def _get_top10_status(available_count: int) -> str:
    if available_count >= 7:
        return "usable"
    if available_count >= 3:
        return "partial"
    return "unavailable"


def build_top10_proxy(fund_code: str) -> tuple[pd.DataFrame, dict]:
    set_log_context(fund_code=fund_code, stage="top10_proxy_build_start")
    logger.info("top10_proxy_build_start fund_code=%s", fund_code)

    holdings, holding_meta = get_fund_holdings(fund_code)
    if holdings.empty:
        set_log_context(stage="top10_proxy_unavailable")
        logger.warning("top10_proxy_unavailable fund_code=%s reason=no_holdings", fund_code)
        return pd.DataFrame(), {
            **holding_meta,
            "proxy_method": "return_inferred_only",
            "top10_proxy_available_count": 0,
            "top10_proxy_missing_count": 0,
            "top10_proxy_status": "unavailable",
            "failed_stock_codes": [],
            "stock_sources_used": {},
            "holding_report_date": None,
            "holding_scope": "unavailable",
        }

    latest_date = holdings["report_date"].max()
    latest = holdings[holdings["report_date"] == latest_date].copy().sort_values("rank").head(10)
    weights = latest.set_index("stock_code")["weight_nav"].astype(float)

    frames = []
    failed = []
    sources_used = {}
    stock_names = latest.set_index("stock_code")["stock_name"].to_dict() if "stock_name" in latest.columns else {}

    for code in weights.index:
        prices, price_meta = get_stock_daily_multi_source(code)
        if prices.empty:
            failed.append(code)
            logger.warning("top10_proxy_stock_failed fund_code=%s stock_code=%s", fund_code, code)
        else:
            frames.append(prices[["date", "ret"]].rename(columns={"ret": code}))
            sources_used[code] = price_meta.get("source", "unknown")
            if code in stock_names:
                logger.info("top10_proxy_stock_success fund_code=%s stock_code=%s stock_name=%s source=%s rows=%s", fund_code, code, stock_names.get(code, ""), price_meta.get("source"), len(prices))

    available_count = len(frames)
    missing_count = len(failed)
    top10_status = _get_top10_status(available_count)

    if not frames:
        set_log_context(stage="top10_proxy_unavailable")
        logger.warning("top10_proxy_unavailable fund_code=%s reason=all_stocks_failed", fund_code)
        return pd.DataFrame(), {
            **holding_meta,
            "proxy_method": "return_inferred_only",
            "top10_proxy_available_count": 0,
            "top10_proxy_missing_count": missing_count,
            "top10_proxy_status": "unavailable",
            "failed_stock_codes": failed,
            "stock_sources_used": sources_used,
            "holding_report_date": latest_date,
            "holding_scope": holding_meta.get("holding_scope", "top10"),
        }

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged = merged.sort_values("date")

    available_codes = [c for c in merged.columns if c != "date"]
    valid_weights = weights.reindex(available_codes).fillna(0)
    if valid_weights.sum() > 0:
        valid_weights = valid_weights / valid_weights.sum()

    proxy_ret = merged[available_codes].mul(valid_weights, axis=1).sum(axis=1, min_count=1)

    out = pd.DataFrame({"date": merged["date"], "top10_proxy_ret": proxy_ret})
    out["top10_proxy_mom5"] = _compound_ret(out["top10_proxy_ret"], 5)
    out["top10_proxy_mom20"] = _compound_ret(out["top10_proxy_ret"], 20)
    out["top10_proxy_vol20"] = out["top10_proxy_ret"].rolling(20).std()
    out["top10_proxy_available_count"] = available_count
    out["top10_proxy_missing_count"] = missing_count
    out["holding_report_date"] = latest_date
    out["holding_scope"] = holding_meta.get("holding_scope", "top10")

    if not out["date"].is_unique:
        logger.error("top10_proxy_date_not_unique fund_code=%s duplicate_count=%s", fund_code, out["date"].duplicated().sum())
        raise ProxyPortfolioError(
            "top10_proxy date 列存在重复值",
            details={"fund_code": fund_code, "duplicate_count": int(out["date"].duplicated().sum())},
        )

    stage = "top10_proxy_build_success" if top10_status == "usable" else "top10_proxy_partial_success" if top10_status == "partial" else "top10_proxy_unavailable"
    set_log_context(stage=stage)
    logger.info("%s fund_code=%s available=%s missing=%s status=%s", stage, fund_code, available_count, missing_count, top10_status)

    return out, {
        **holding_meta,
        "proxy_method": "top10_proxy" if top10_status == "usable" else "partial_top10_proxy" if top10_status == "partial" else "return_inferred_only",
        "top10_proxy_available_count": available_count,
        "top10_proxy_missing_count": missing_count,
        "top10_proxy_status": top10_status,
        "failed_stock_codes": failed,
        "stock_sources_used": sources_used,
        "holding_report_date": latest_date,
        "holding_scope": holding_meta.get("holding_scope", "top10"),
    }


def _fetch_theme(theme_name: str, symbol: str, proxy_name: str) -> pd.DataFrame:
    path = RAW_DIR / "theme_index" / f"{theme_name}.csv"
    if path.exists():
        return pd.read_csv(path, parse_dates=["date"])
    df, _ = get_index_daily(symbol, require_fresh=False)
    out = df[["date", "close"]].copy()
    out["ret"] = out["close"].pct_change()
    out["source"] = "index_theme_proxy"
    out["proxy_symbol"] = symbol
    out["proxy_name"] = proxy_name
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    return out


def build_theme_proxy() -> tuple[pd.DataFrame, dict]:
    set_log_context(stage="theme_proxy_fetch_start")
    logger.info("theme_proxy_fetch_start")
    frames = []
    failed = []
    for name, (_, symbol, proxy_name) in THEME_PROXIES.items():
        try:
            df = _fetch_theme(name, symbol, proxy_name)
            if df.empty:
                raise RuntimeError("empty theme data")
            frames.append(df[["date", "ret"]].rename(columns={"ret": f"theme_{name}_ret"}))
        except Exception:
            set_log_context(stage="theme_proxy_fetch_warning")
            logger.exception("theme_proxy_fetch_warning theme=%s", name)
            failed.append(name)

    if not frames:
        return pd.DataFrame(), {"theme_available_count": 0, "failed_themes": failed}

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged = merged.sort_values("date")
    ret_cols = [c for c in merged.columns if c.startswith("theme_") and c.endswith("_ret")]
    for col in ret_cols:
        base = col.removesuffix("_ret")
        merged[f"{base}_mom5"] = _compound_ret(merged[col], 5)
        merged[f"{base}_mom20"] = _compound_ret(merged[col], 20)
        merged[f"{base}_vol20"] = merged[col].rolling(20).std()

    merged["theme_proxy_ret"] = merged[ret_cols].mean(axis=1)
    merged["theme_proxy_mom5"] = _compound_ret(merged["theme_proxy_ret"], 5)
    merged["theme_proxy_mom20"] = _compound_ret(merged["theme_proxy_ret"], 20)
    merged["theme_proxy_vol20"] = merged["theme_proxy_ret"].rolling(20).std()
    set_log_context(stage="theme_proxy_fetch_success")
    logger.info("theme_proxy_fetch_success available=%s failed=%s", len(ret_cols), len(failed))
    return merged, {"theme_available_count": len(ret_cols), "failed_themes": failed}


def add_theme_relative_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ret_cols = [c for c in out.columns if c.startswith("theme_") and c.endswith("_ret")]
    for col in ret_cols:
        base = col.removesuffix("_ret")
        if "hs300_ret" in out.columns:
            out[f"{base}_vs_hs300"] = out[col] - out["hs300_ret"]
        if "cyb_ret" in out.columns:
            out[f"{base}_vs_cyb"] = out[col] - out["cyb_ret"]
    return out


def fit_rolling_proxy_exposure(df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    set_log_context(stage="rolling_proxy_exposure_start")
    logger.info("rolling_proxy_exposure_start")

    cols = ["top10_proxy_ret", "theme_proxy_ret", "hs300_ret", "cyb_ret", "kcb50_ret", "zz1000_ret", "style_tech_vs_large"]
    names = ["top10", "theme", "hs300", "cyb", "kcb50", "zz1000", "style_tech"]

    out = pd.DataFrame(index=df.index)
    for name in names:
        out[f"beta_{name}_60"] = np.nan
    out["proxy_r2_60"] = np.nan
    out["tracking_error_60"] = np.nan
    out["proxy_pred_ret_60"] = np.nan
    out["proxy_residual"] = np.nan

    for i in range(window - 1, len(df)):
        sample = df.iloc[i - window + 1 : i + 1][["fund_ret"] + cols].dropna(subset=["fund_ret"])
        if len(sample) < 40:
            continue
        try:
            active_pairs = [(col, name) for col, name in zip(cols, names) if sample[col].notna().any()]
            if len(active_pairs) < 2:
                continue
            active_cols = [p[0] for p in active_pairs]
            active_names = [p[1] for p in active_pairs]
            imputer = SimpleImputer(strategy="median")
            x = imputer.fit_transform(sample[active_cols])
            y = sample["fund_ret"].to_numpy()
            model = Ridge(alpha=1.0)
            model.fit(x, y)
            fitted = model.predict(x)
            resid = y - fitted
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            ss_res = float(np.sum(resid**2))
            latest_x = imputer.transform(df.iloc[[i]][active_cols])
            pred = float(model.predict(latest_x)[0])
            for name, beta in zip(active_names, model.coef_):
                out.loc[df.index[i], f"beta_{name}_60"] = float(beta)
            out.loc[df.index[i], "proxy_r2_60"] = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
            out.loc[df.index[i], "tracking_error_60"] = float(np.std(resid, ddof=1))
            out.loc[df.index[i], "proxy_pred_ret_60"] = pred
            out.loc[df.index[i], "proxy_residual"] = float(df.iloc[i]["fund_ret"] - pred) if pd.notna(df.iloc[i]["fund_ret"]) else np.nan
        except Exception:
            logger.exception("rolling_proxy_exposure_window_failed index=%s", i)

    out["proxy_residual_mom5"] = out["proxy_residual"].rolling(5).mean()
    out["proxy_residual_vol20"] = out["proxy_residual"].rolling(20).std()
    out["proxy_quality_flag"] = np.select(
        [out["proxy_r2_60"] >= 0.60, out["proxy_r2_60"] >= 0.35],
        ["high", "medium"],
        default="low",
    )
    set_log_context(stage="rolling_proxy_exposure_success")
    logger.info("rolling_proxy_exposure_success")
    return out


def _safe_scalar(value):
    if isinstance(value, pd.Series):
        value = value.dropna()
        if value.empty:
            return None
        return value.iloc[-1]
    return value


def _get_top_exposures(row: pd.Series, beta_cols: list[str], top_n: int = 3) -> list[dict]:
    exposures = []
    for col in beta_cols:
        raw_val = row.get(col, None)
        val = _safe_scalar(raw_val)
        if val is None or pd.isna(val):
            continue
        try:
            beta = float(val)
        except Exception:
            continue
        name = col.replace("beta_", "").replace("_60", "")
        exposures.append({"name": name, "beta": abs(beta), "sign": "positive" if beta >= 0 else "negative"})
    exposures.sort(key=lambda x: x["beta"], reverse=True)
    return exposures[:top_n]


def build_proxy_exposure_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"top_exposures": [], "proxy_r2_60": None, "tracking_error_60": None, "proxy_quality_flag": "low"}

    latest = df.iloc[-1]
    beta_cols = [c for c in df.columns if c.startswith("beta_") and c.endswith("_60")]
    top_exposures = _get_top_exposures(latest, beta_cols)

    proxy_r2 = latest.get("proxy_r2_60")
    tracking_error = latest.get("tracking_error_60")
    quality = latest.get("proxy_quality_flag", "low")

    return {
        "top_exposures": top_exposures,
        "proxy_r2_60": float(proxy_r2) if pd.notna(proxy_r2) else None,
        "tracking_error_60": float(tracking_error) if pd.notna(tracking_error) else None,
        "proxy_quality_flag": quality if pd.notna(quality) else "low",
    }


def build_proxy_features(fund_code: str, base_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    try:
        top10, holding_meta = build_top10_proxy(fund_code)
        theme, theme_meta = build_theme_proxy()
        out = base_df.copy()
        if not top10.empty:
            out = out.merge(top10, on="date", how="left")
        if not theme.empty:
            out = out.merge(theme, on="date", how="left")
        if "top10_proxy_ret" not in out.columns:
            out["top10_proxy_ret"] = np.nan
        if "theme_proxy_ret" not in out.columns:
            out["theme_proxy_ret"] = np.nan
        out = add_theme_relative_features(out)
        exposure = fit_rolling_proxy_exposure(out)
        out = pd.concat([out, exposure], axis=1)

        duplicated_cols = out.columns[out.columns.duplicated()].tolist()
        if duplicated_cols:
            logger.error("duplicate_feature_columns fund_code=%s columns=%s", fund_code, duplicated_cols[:20])
            raise DuplicateFeatureColumnsError(
                f"特征表存在重复列名: {duplicated_cols[:20]}",
                details={"fund_code": fund_code, "duplicated_columns": duplicated_cols[:20]},
            )

        exposure_summary = build_proxy_exposure_summary(out)

        meta = {
            "proxy_available": bool((not top10.empty) or (not theme.empty)),
            **holding_meta,
            **theme_meta,
            "exposure_summary": exposure_summary,
        }
        set_log_context(stage="proxy_feature_merge_success")
        logger.info("proxy_feature_merge_success proxy_available=%s top10_status=%s proxy_r2_60=%s", meta["proxy_available"], holding_meta.get("top10_proxy_status"), exposure_summary.get("proxy_r2_60"))
        return out, meta
    except DuplicateFeatureColumnsError:
        raise
    except Exception as exc:
        logger.exception("proxy_portfolio_failed")
        return base_df, {"proxy_available": False, "proxy_method": "return_inferred_only", "reason": str(exc)}
