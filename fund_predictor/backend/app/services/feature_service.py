import logging

import numpy as np
import pandas as pd

from app.core.config import MIN_TRAIN_ROWS, PROCESSED_DIR
from app.core.errors import AppError, DuplicateFeatureColumnsError, FeatureBuildError, InsufficientDataError
from app.core.logging_config import set_log_context
from app.services.data_service import get_fund_nav, load_market_data
from app.services.proxy_portfolio_service import build_proxy_features

logger = logging.getLogger(__name__)


def _ret(series: pd.Series) -> pd.Series:
    return series.pct_change()


def _drawdown(series: pd.Series, window: int) -> pd.Series:
    peak = series.rolling(window).max()
    return series / peak - 1.0


def _consecutive_count(is_event: pd.Series) -> pd.Series:
    counts = []
    current = 0
    for value in is_event.fillna(False):
        current = current + 1 if value else 0
        counts.append(current)
    return pd.Series(counts, index=is_event.index)


def _rolling_beta(df: pd.DataFrame, y_col: str, x_cols: list[str], window: int = 60) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col in x_cols:
        out[f"beta_{col.replace('_ret', '')}_{window}"] = np.nan
    out[f"beta_r2_{window}"] = np.nan
    out[f"residual_vol_{window}"] = np.nan
    for i in range(window - 1, len(df)):
        sample = df.iloc[i - window + 1 : i + 1][[y_col] + x_cols].dropna()
        if len(sample) < max(30, len(x_cols) + 5):
            continue
        y = sample[y_col].to_numpy()
        x = sample[x_cols].to_numpy()
        x_design = np.column_stack([np.ones(len(x)), x])
        try:
            coef, *_ = np.linalg.lstsq(x_design, y, rcond=None)
            fitted = x_design @ coef
            resid = y - fitted
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            ss_res = float(np.sum(resid**2))
            for col, beta in zip(x_cols, coef[1:]):
                out.loc[df.index[i], f"beta_{col.replace('_ret', '')}_{window}"] = float(beta)
            out.loc[df.index[i], f"beta_r2_{window}"] = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
            out.loc[df.index[i], f"residual_vol_{window}"] = float(np.std(resid, ddof=1))
        except Exception:
            logger.exception("rolling_beta_failed index=%s", i)
    return out


def _insufficient_nav_error(fund_code: str, fund: pd.DataFrame, fund_meta: dict) -> InsufficientDataError:
    return InsufficientDataError(
        f"Fund NAV rows are insufficient: {len(fund)} rows, need at least {MIN_TRAIN_ROWS + 1}",
        details={
            "fund_code": fund_code,
            "nav_rows": int(len(fund)),
            "nav_start_date": str(pd.to_datetime(fund["date"]).min().date()) if len(fund) else None,
            "nav_end_date": str(pd.to_datetime(fund["date"]).max().date()) if len(fund) else None,
            "nav_source": fund_meta.get("nav_source") or fund_meta.get("source_used"),
            "source_used": fund_meta.get("source_used"),
            "fallback_used": fund_meta.get("fallback_used", False),
            "fallback_reason": fund_meta.get("fallback_reason"),
            "min_required_rows": MIN_TRAIN_ROWS + 1,
            "suspected_reason": "history_nav_truncated_or_wrong_api",
        },
    )


def build_features(fund_code: str, require_fresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    set_log_context(fund_code=fund_code, stage="feature_build_start")
    logger.info("feature_build_start")
    try:
        fund, fund_meta = get_fund_nav(fund_code, require_fresh=require_fresh)
        if len(fund) < MIN_TRAIN_ROWS + 1:
            raise _insufficient_nav_error(fund_code, fund, fund_meta)

        indexes, index_meta = load_market_data(require_fresh=require_fresh)
        df = fund[["date", "nav", "acc_nav", "daily_growth_pct"]].copy()
        df["fund_ret"] = _ret(df["acc_nav"].replace(0, np.nan))
        if df["fund_ret"].isna().mean() > 0.5:
            df["fund_ret"] = df["daily_growth_pct"] / 100.0

        for lag in [1, 2, 3, 5, 10]:
            df[f"fund_ret_lag{lag}"] = df["fund_ret"].shift(lag)
        for win in [5, 10, 20, 60]:
            df[f"fund_ret_mean_{win}"] = df["fund_ret"].rolling(win).mean()
            df[f"fund_ret_std_{win}"] = df["fund_ret"].rolling(win).std()
            df[f"fund_mom_{win}"] = df["acc_nav"].pct_change(win)
        for win in [20, 60]:
            df[f"fund_drawdown_{win}"] = _drawdown(df["acc_nav"], win)
        df["recent_max_gain_20"] = df["fund_ret"].rolling(20).max()
        df["recent_max_loss_20"] = df["fund_ret"].rolling(20).min()
        df["up_days_5"] = (df["fund_ret"] > 0).rolling(5).sum()
        df["down_days_5"] = (df["fund_ret"] < 0).rolling(5).sum()
        df["consecutive_up_days"] = _consecutive_count(df["fund_ret"] > 0)
        df["consecutive_down_days"] = _consecutive_count(df["fund_ret"] < 0)

        for name, idx in indexes.items():
            idx_df = idx[["date", "close", "volume"]].copy()
            idx_df[f"{name}_ret"] = _ret(idx_df["close"])
            idx_df[f"{name}_ret_lag1"] = idx_df[f"{name}_ret"].shift(1)
            for win in [5, 20]:
                idx_df[f"{name}_ret_mean_{win}"] = idx_df[f"{name}_ret"].rolling(win).mean()
                idx_df[f"{name}_ret_std_{win}"] = idx_df[f"{name}_ret"].rolling(win).std()
                idx_df[f"{name}_mom_{win}"] = idx_df["close"].pct_change(win)
                idx_df[f"{name}_volume_chg_{win}"] = idx_df["volume"].pct_change(win)
            idx_df[f"{name}_vol_20"] = idx_df[f"{name}_ret"].rolling(20).std()
            keep = ["date"] + [c for c in idx_df.columns if c.startswith(f"{name}_") and not c.endswith("_volume")]
            df = df.merge(idx_df[keep], on="date", how="left")

        _available_index_rets = [c for c in df.columns if c.endswith("_ret") and not c.startswith("fund_")]
        logger.info("available_index_returns fund_code=%s indexes=%s", fund_code, _available_index_rets)

        if "cyb_ret" in df.columns and "hs300_ret" in df.columns:
            df["style_growth_vs_large"] = df["cyb_ret"] - df["hs300_ret"]
        if "zz1000_ret" in df.columns and "hs300_ret" in df.columns:
            df["style_small_vs_large"] = df["zz1000_ret"] - df["hs300_ret"]
        if "kcb50_ret" in df.columns and "hs300_ret" in df.columns:
            df["style_tech_vs_large"] = df["kcb50_ret"] - df["hs300_ret"]
        for col in ["style_growth_vs_large", "style_small_vs_large", "style_tech_vs_large"]:
            if col in df.columns:
                df[f"{col}_mean_5"] = df[col].rolling(5).mean()
                df[f"{col}_mean_20"] = df[col].rolling(20).mean()
        df, proxy_meta = build_proxy_features(fund_code, df)

        duplicated_cols = df.columns[df.columns.duplicated()].tolist()
        if duplicated_cols:
            logger.error("duplicate_feature_columns fund_code=%s columns=%s", fund_code, duplicated_cols[:20])
            raise DuplicateFeatureColumnsError(
                f"特征表存在重复列名: {duplicated_cols[:20]}",
                details={"fund_code": fund_code, "duplicated_columns": duplicated_cols[:20]},
            )

        # 修复日期口径：明确区分特征日期和目标日期
        df["feature_date"] = df["date"]
        df["target_date"] = df["date"].shift(-1)
        
        df["target_next"] = df["fund_ret"].shift(-1)

        # 相对收益目标 (V2.6)
        set_log_context(stage="excess_target_build_start")
        logger.info("excess_target_build_start fund_code=%s", fund_code)
        
        if "cyb_ret" in df.columns:
            df["target_excess_cyb"] = df["fund_ret"].shift(-1) - df["cyb_ret"].shift(-1)
        if "kcb50_ret" in df.columns:
            df["target_excess_kcb50"] = df["fund_ret"].shift(-1) - df["kcb50_ret"].shift(-1)
        if "top10_proxy_ret" in df.columns:
            df["target_excess_top10"] = df["fund_ret"].shift(-1) - df["top10_proxy_ret"].shift(-1)
        if "theme_proxy_ret" in df.columns:
            df["target_excess_theme"] = df["fund_ret"].shift(-1) - df["theme_proxy_ret"].shift(-1)
        
        set_log_context(stage="excess_target_build_success")
        logger.info("excess_target_build_success fund_code=%s excess_targets=%s", fund_code, 
                    [c for c in df.columns if c.startswith("target_excess_")])

        # 暴露稳定性指标 (V2.6)
        if "proxy_r2_60" in df.columns:
            df["proxy_r2_mean_20"] = df["proxy_r2_60"].rolling(20).mean()
            df["proxy_r2_trend_20"] = df["proxy_r2_60"].diff(20)
        if "tracking_error_60" in df.columns:
            df["tracking_error_mean_20"] = df["tracking_error_60"].rolling(20).mean()
        
        set_log_context(stage="exposure_stability_check_success")
        logger.info("exposure_stability_check_success fund_code=%s", fund_code)

        banned = [c for c in df.columns if c.endswith(("_open", "_close", "_high", "_low", "_volume"))]
        df = df.drop(columns=banned, errors="ignore")
        df = df.replace([np.inf, -np.inf], np.nan).sort_values("date").reset_index(drop=True)
        train = df.dropna(subset=["target_next"]).copy()
        feature_count = len(model_feature_columns(df))

        logger.info(
            "data_self_check fund_code=%s nav_rows=%s nav_start_date=%s nav_end_date=%s dataset_rows=%s data_train_rows=%s feature_count=%s source_used=%s fallback_used=%s",
            fund_code,
            len(fund),
            str(pd.to_datetime(fund["date"]).min().date()),
            str(pd.to_datetime(fund["date"]).max().date()),
            len(df),
            len(train),
            feature_count,
            fund_meta.get("source_used"),
            fund_meta.get("fallback_used"),
        )

        if len(train) < MIN_TRAIN_ROWS:
            raise InsufficientDataError(
                f"Training rows are insufficient: {len(train)} rows, need at least {MIN_TRAIN_ROWS}",
                details={
                    "fund_code": fund_code,
                    "nav_rows": int(len(fund)),
                    "nav_start_date": str(pd.to_datetime(fund["date"]).min().date()),
                    "nav_end_date": str(pd.to_datetime(fund["date"]).max().date()),
                    "nav_source": fund_meta.get("nav_source") or fund_meta.get("source_used"),
                    "source_used": fund_meta.get("source_used"),
                    "fallback_used": fund_meta.get("fallback_used", False),
                    "fallback_reason": fund_meta.get("fallback_reason"),
                    "dataset_rows": int(len(df)),
                    "data_train_rows": int(len(train)),
                    "feature_count": feature_count,
                    "min_required_rows": MIN_TRAIN_ROWS,
                    "suspected_reason": "feature_warmup_or_target_rows_insufficient",
                },
            )

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(PROCESSED_DIR / f"dataset_{fund_code}.csv", index=False, encoding="utf-8")
        set_log_context(stage="feature_build_success")
        logger.info("feature_build_success rows_full=%s rows_train=%s", len(df), len(train))
        meta = {
            "fund": fund_meta,
            "indexes": index_meta,
            "proxy": proxy_meta,
            "stale": bool(fund_meta.get("stale") or any(i.get("stale") for i in index_meta)),
        }
        return df, train, meta
    except AppError:
        raise
    except Exception as exc:
        set_log_context(stage="feature_build_failed")
        logger.exception("feature_build_failed")
        raise FeatureBuildError("Feature build failed", details={"reason": str(exc), "fund_code": fund_code}) from exc


def model_feature_columns(df: pd.DataFrame) -> list[str]:
    """
    筛选模型特征列，严格排除所有未来标签列以防止数据泄露
    
    排除规则：
    - date: 日期列
    - feature_date: 特征日期（与date相同）
    - target_date: 目标日期（T+1）
    - target_next: 下一期收益目标
    - target_*: 所有目标列（包括 target_excess_*）
    - nav/acc_nav: 原始净值列
    - open/high/low/close/volume: 原始价格量列
    - 包含 target/next/future/label 的列名
    """
    # 基础排除集合
    excluded_exact = {
        "date", "feature_date", "target_date", 
        "target_next", "nav", "acc_nav"
    }
    
    # 禁止的后缀
    banned_suffixes = ("_open", "_close", "_high", "_low", "_volume")
    
    # 禁止的子字符串（用于检测泄露相关列）
    # 注意：这里检查整个列名是否包含这些关键词
    banned_keywords = ("target", "next", "future", "label")
    
    feature_cols = []
    for c in df.columns:
        # 检查是否精确匹配排除项
        if c in excluded_exact:
            continue
        
        # 检查后缀
        if c.endswith(banned_suffixes):
            continue
        
        # 检查是否包含泄露相关关键词（不区分大小写）
        col_lower = c.lower()
        if any(keyword in col_lower for keyword in banned_keywords):
            continue
        
        # 检查是否为数值类型且有有效值
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if not df[c].notna().any():
            continue
        
        feature_cols.append(c)
    
    return feature_cols


def validate_no_leakage_columns(feature_cols: list[str], fund_code: str) -> None:
    """
    训练前硬检查：确保没有泄露列进入特征
    
    如果发现有 target/next/future/label 相关列，立即抛出异常
    """
    # 泄露检测关键词（与 model_feature_columns 保持一致）
    leakage_keywords = {
        "target": "目标列",
        "next": "未来值列", 
        "future": "未来值列",
        "label": "标签列",
    }
    
    bad_cols = []
    leakage_reasons = {}
    
    for col in feature_cols:
        col_lower = col.lower()
        for keyword, reason in leakage_keywords.items():
            if keyword in col_lower:
                bad_cols.append(col)
                leakage_reasons[col] = reason
                break
    
    if bad_cols:
        logger.error(
            "data_leakage_detected fund_code=%s bad_cols=%s",
            fund_code,
            bad_cols[:20]
        )
        raise FeatureBuildError(
            "发现未来标签列进入特征，存在数据泄露风险",
            details={
                "fund_code": fund_code,
                "bad_feature_cols": bad_cols[:50],
                "leakage_reasons": leakage_reasons,
                "total_bad_cols": len(bad_cols),
                "suggestion": "请检查 feature_service 中的 model_feature_columns 函数，确保正确排除所有 target/next/future/label 列",
            },
        )
    
    logger.info("leakage_check_passed fund_code=%s feature_count=%s", fund_code, len(feature_cols))
