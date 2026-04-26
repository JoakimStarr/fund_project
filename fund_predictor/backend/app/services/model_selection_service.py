import itertools
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.feature_selection import SelectKBest, f_classif, f_regression, mutual_info_classif, mutual_info_regression
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import BayesianRidge, ElasticNet, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler

# XGB/LightGBM 可选导入 (V2.6)
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    xgb = None
    XGB_AVAILABLE = False
    logger.warning("xgboost_not_available")

try:
    import lightgbm as lgb
    LGBM_AVAILABLE = True
except ImportError:
    lgb = None
    LGBM_AVAILABLE = False
    logger.warning("lightgbm_not_available")

from backend.app.core.config import INTERVAL_ALPHA
from backend.app.core.errors import BaselineEvalError, ModelSelectionError, ProbabilityCalibrationError, RegimeIntervalError
from backend.app.core.logging_config import set_log_context
from backend.app.services.feature_service import model_feature_columns

logger = logging.getLogger("train")

PREDICTION_MODE = "t_plus_1_close"
TRAIN_WINDOW = 180


@dataclass
class ModelBundle:
    point_model_name: str
    direction_model_name: str | None
    point_pipeline: Pipeline
    direction_pipeline: Any | None
    selected_features_point: list[str]
    selected_features_direction: list[str]
    interval_config: dict[str, Any]


def _split_train_valid_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    train_end = int(n * 0.65)
    valid_end = int(n * 0.82)
    return df.iloc[:train_end].copy(), df.iloc[train_end:valid_end].copy(), df.iloc[valid_end:].copy()


def _selector(selector: str, n_features: int, task: str):
    if selector == "all":
        return "passthrough"
    kind, top = selector.split("_top")
    k = min(int(top), n_features)
    if task == "classification":
        return SelectKBest(f_classif if kind == "f" else mutual_info_classif, k=k)
    return SelectKBest(f_regression if kind == "f" else mutual_info_regression, k=k)


def _make_pipeline(selector: str, scaler_name: str, model, n_features: int, task: str) -> Pipeline:
    scaler = StandardScaler() if scaler_name == "standard" else RobustScaler()
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", scaler),
            ("selector", _selector(selector, n_features, task)),
            ("model", model),
        ]
    )


def _selected_features(pipe: Pipeline, feature_cols: list[str]) -> list[str]:
    selector = pipe.named_steps["selector"]
    if selector == "passthrough":
        return feature_cols
    return [c for c, keep in zip(feature_cols, selector.get_support()) if keep]


def _regressors() -> dict[str, Any]:
    models = {
        "ridge": Ridge(alpha=1.0),
        "bayesian_ridge": BayesianRidge(),
        "elastic_net": ElasticNet(alpha=0.001, l1_ratio=0.2, max_iter=5000),
        "extra_trees": ExtraTreesRegressor(n_estimators=120, max_depth=5, random_state=42, n_jobs=-1),
        "random_forest": RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1),
        "hist_gbr": HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=15, random_state=42),
        "gbr": GradientBoostingRegressor(n_estimators=120, max_depth=2, random_state=42),
    }
    # XGB/LightGBM 候选 (V2.6)
    if XGB_AVAILABLE and xgb is not None:
        models["xgboost"] = xgb.XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42, n_jobs=-1, verbosity=0)
    if LGBM_AVAILABLE and lgb is not None:
        models["lightgbm"] = lgb.LGBMRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, n_jobs=-1, verbose=-1)
    return models


def _classifiers() -> dict[str, Any]:
    models = {
        "logistic": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "extra_trees_cls": ExtraTreesClassifier(n_estimators=160, max_depth=5, random_state=42, n_jobs=-1, class_weight="balanced"),
        "random_forest_cls": RandomForestClassifier(n_estimators=140, max_depth=5, random_state=42, n_jobs=-1, class_weight="balanced"),
        "hist_gbc": HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=15, random_state=42),
    }
    # XGB/LightGBM 候选 (V2.6)
    if XGB_AVAILABLE and xgb is not None:
        models["xgboost_cls"] = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42, n_jobs=-1, verbosity=0)
    if LGBM_AVAILABLE and lgb is not None:
        models["lightgbm_cls"] = lgb.LGBMClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, n_jobs=-1, verbose=-1)
    return models


def _candidates(models: dict[str, Any]) -> list[tuple[str, str, str, Any]]:
    selectors = ["all", "f_top10", "f_top20", "f_top40", "mi_top10", "mi_top20", "mi_top40"]
    return [(name, selector, scaler, model) for name, model in models.items() for selector, scaler in itertools.product(selectors, ["standard", "robust"])]


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, baseline_mean: np.ndarray | None = None) -> dict[str, float]:
    ae = np.abs(y_true - y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    p90 = float(np.quantile(ae, 0.90))
    corr = float(np.corrcoef(y_true, y_pred)[0, 1]) if np.std(y_pred) > 0 and np.std(y_true) > 0 else 0.0
    std_ratio = float(np.std(y_pred) / np.std(y_true)) if np.std(y_true) > 0 else 0.0
    zero_rmse = float(np.sqrt(mean_squared_error(y_true, np.zeros_like(y_true))))
    mean_pred = baseline_mean if baseline_mean is not None else np.full_like(y_true, np.mean(y_true))
    mean_rmse = float(np.sqrt(mean_squared_error(y_true, mean_pred)))
    improvement_zero = float((zero_rmse - rmse) / zero_rmse) if zero_rmse > 0 else 0.0
    improvement_mean = float((mean_rmse - rmse) / mean_rmse) if mean_rmse > 0 else 0.0
    q90 = p90
    width = 2 * q90
    score = 0.45 * rmse + 0.25 * mae + 0.15 * p90 + 0.05 * abs(0.90 - INTERVAL_ALPHA) + 0.20 * width
    return {
        "rmse": rmse,
        "mae": mae,
        "p90_ae": p90,
        "rmse_bp": rmse * 10000,
        "mae_bp": mae * 10000,
        "p90_ae_bp": p90 * 10000,
        "pred_real_corr": corr,
        "pred_real_std_ratio": std_ratio,
        "baseline_zero_rmse_bp": zero_rmse * 10000,
        "baseline_mean_rmse_bp": mean_rmse * 10000,
        "model_vs_zero_improvement": improvement_zero,
        "model_vs_mean_improvement": improvement_mean,
        "flat_prediction": bool(std_ratio < 0.15),
        "low_correlation": bool(corr < 0.10),
        "near_baseline": bool(improvement_mean < 0.05),
        "score": float(score),
    }


def _rolling_baselines(data_train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    set_log_context(stage="baseline_eval_start")
    logger.info("baseline_eval_start")
    try:
        target = data_train["target_next"]
        rows = []
        for idx in test.index:
            pos = data_train.index.get_loc(idx)
            hist = target.iloc[max(0, pos - TRAIN_WINDOW) : pos].dropna()
            prev = target.iloc[pos - 1] if pos > 0 else 0.0
            rows.append(
                {
                    "rolling_mean": float(hist.mean()) if len(hist) else 0.0,
                    "rolling_median": float(hist.median()) if len(hist) else 0.0,
                    "last_ret": float(prev) if pd.notna(prev) else 0.0,
                    "rolling_positive_rate": float((hist > 0).mean()) if len(hist) else 0.5,
                }
            )
        out = pd.DataFrame(rows, index=test.index)
        set_log_context(stage="baseline_eval_success")
        logger.info("baseline_eval_success")
        return out
    except Exception as exc:
        logger.exception("baseline_eval_failed")
        raise BaselineEvalError("Baseline evaluation failed", details={"reason": str(exc)}) from exc


def _point_model(data_train: pd.DataFrame, feature_cols: list[str], progress_cb=None):
    set_log_context(stage="point_model_train_start")
    logger.info("point_model_train_start")
    train_base, valid, test = _split_train_valid_test(data_train)
    X_train, y_train = train_base[feature_cols], train_base["target_next"]
    X_valid, y_valid = valid[feature_cols], valid["target_next"]
    rough = []
    if progress_cb:
        progress_cb(35, "point_model_train_start", "Training point model candidates")
    for model_name, selector, scaler, model in _candidates(_regressors()):
        try:
            pipe = _make_pipeline(selector, scaler, clone(model), len(feature_cols), "regression")
            pipe.fit(X_train, y_train)
            pred = pipe.predict(X_valid)
            rough.append({"model": model_name, "selector": selector, "scaler": scaler, "metrics": _regression_metrics(y_valid.to_numpy(), pred)})
        except Exception:
            logger.exception("point_candidate_failed rough model=%s selector=%s scaler=%s", model_name, selector, scaler)
    if not rough:
        raise ModelSelectionError("No point model passed rough search")
    top20 = sorted(rough, key=lambda x: x["metrics"]["score"])[:20]

    rolling = []
    combined = pd.concat([train_base, valid])
    if progress_cb:
        progress_cb(50, "point_model_train_start", "Refining point model with walk-forward")
    for item in top20:
        preds, trues = [], []
        start = max(120, len(combined) - 120)
        for i in range(start, len(combined)):
            w = combined.iloc[max(0, i - TRAIN_WINDOW) : i]
            if len(w) < 120:
                continue
            pipe = _make_pipeline(item["selector"], item["scaler"], clone(_regressors()[item["model"]]), len(feature_cols), "regression")
            pipe.fit(w[feature_cols], w["target_next"])
            preds.append(float(pipe.predict(combined.iloc[[i]][feature_cols])[0]))
            trues.append(float(combined.iloc[i]["target_next"]))
        if preds:
            rolling.append({**item, "rolling_metrics": _regression_metrics(np.array(trues), np.array(preds))})
    top5 = sorted(rolling or top20, key=lambda x: x.get("rolling_metrics", x["metrics"])["score"])[:5]

    baselines = _rolling_baselines(data_train, test)
    final = []
    train_valid = pd.concat([train_base, valid])
    for item in top5:
        try:
            pipe = _make_pipeline(item["selector"], item["scaler"], clone(_regressors()[item["model"]]), len(feature_cols), "regression")
            pipe.fit(train_valid[feature_cols], train_valid["target_next"])
            pred = pipe.predict(test[feature_cols])
            metrics = _regression_metrics(test["target_next"].to_numpy(), pred, baseline_mean=baselines["rolling_mean"].to_numpy())
            final.append({**item, "pipeline": pipe, "pred": pred, "final_metrics": metrics})
        except Exception:
            logger.exception("point_candidate_failed final model=%s", item["model"])
    if not final:
        raise ModelSelectionError("No point model passed final test")
    best = sorted(final, key=lambda x: x["final_metrics"]["score"])[0]
    final_pipe = _make_pipeline(best["selector"], best["scaler"], clone(_regressors()[best["model"]]), len(feature_cols), "regression")
    final_pipe.fit(data_train[feature_cols], data_train["target_next"])
    set_log_context(stage="point_model_train_success")
    logger.info("point_model_train_success model=%s selector=%s", best["model"], best["selector"])
    return best, final_pipe, _selected_features(final_pipe, feature_cols), test, baselines


def _is_proxy_feature(col: str) -> bool:
    return (
        col.startswith("top10_proxy_")
        or col.startswith("theme_")
        or col.startswith("beta_top10_")
        or col.startswith("beta_theme_")
        or col.startswith("beta_style_tech_")
        or col in {
            "proxy_r2_60",
            "tracking_error_60",
            "proxy_pred_ret_60",
            "proxy_residual",
            "proxy_residual_mom5",
            "proxy_residual_vol20",
        }
    )


def _proxy_gain_eval(data_train: pd.DataFrame, feature_cols: list[str], point_best: dict, test: pd.DataFrame, baselines: pd.DataFrame) -> dict[str, Any]:
    set_log_context(stage="proxy_feature_gain_eval_start")
    logger.info("proxy_feature_gain_eval_start")
    proxy_cols = [c for c in feature_cols if _is_proxy_feature(c)]
    no_proxy_cols = [c for c in feature_cols if c not in proxy_cols]
    if not proxy_cols or len(no_proxy_cols) < 5:
        return {
            "before_proxy_metrics": None,
            "after_proxy_metrics": point_best["final_metrics"],
            "proxy_feature_gain": None,
            "proxy_features_helpful": False,
            "proxy_feature_count": len(proxy_cols),
        }
    train_base, valid, _ = _split_train_valid_test(data_train)
    train_valid = pd.concat([train_base, valid])
    try:
        before_pipe = _make_pipeline(point_best["selector"], point_best["scaler"], clone(_regressors()[point_best["model"]]), len(no_proxy_cols), "regression")
        before_pipe.fit(train_valid[no_proxy_cols], train_valid["target_next"])
        before_pred = before_pipe.predict(test[no_proxy_cols])
        before = _regression_metrics(test["target_next"].to_numpy(), before_pred, baseline_mean=baselines["rolling_mean"].to_numpy())
        after = point_best["final_metrics"]
        gain = {
            "rmse_improvement": before["rmse"] - after["rmse"],
            "mae_improvement": before["mae"] - after["mae"],
            "corr_improvement": after["pred_real_corr"] - before["pred_real_corr"],
            "std_ratio_improvement": after["pred_real_std_ratio"] - before["pred_real_std_ratio"],
            "mean_baseline_improvement_delta": after["model_vs_mean_improvement"] - before["model_vs_mean_improvement"],
        }
        helpful = bool(gain["rmse_improvement"] > 0 and gain["corr_improvement"] > 0)
        set_log_context(stage="proxy_feature_gain_eval_success")
        logger.info("proxy_feature_gain_eval_success helpful=%s gain=%s", helpful, gain)
        return {
            "before_proxy_metrics": before,
            "after_proxy_metrics": after,
            "proxy_feature_gain": gain,
            "proxy_features_helpful": helpful,
            "proxy_feature_count": len(proxy_cols),
        }
    except Exception:
        logger.exception("proxy_feature_gain_eval_failed")
        return {
            "before_proxy_metrics": None,
            "after_proxy_metrics": point_best["final_metrics"],
            "proxy_feature_gain": None,
            "proxy_features_helpful": False,
            "proxy_feature_count": len(proxy_cols),
        }


def _calibrated_direction_pipeline(base_pipe: Pipeline, x_calib: pd.DataFrame, y_calib: pd.Series):
    set_log_context(stage="direction_model_calibration_start")
    logger.info("direction_model_calibration_start")
    if y_calib.nunique() < 2:
        raise ProbabilityCalibrationError("Calibration window has only one class")
    try:
        calibrated = CalibratedClassifierCV(FrozenEstimator(base_pipe), method="sigmoid")
        calibrated.fit(x_calib, y_calib)
        set_log_context(stage="direction_model_calibration_success")
        logger.info("direction_model_calibration_success")
        return calibrated
    except Exception as exc:
        logger.exception("direction_model_calibration_failed")
        raise ProbabilityCalibrationError("Probability calibration failed", details={"reason": str(exc)}) from exc


def _calibration_error(y_true: np.ndarray, p_up: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    err = 0.0
    total = len(y_true)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p_up >= lo) & (p_up < hi if hi < 1 else p_up <= hi)
        if np.any(mask):
            err += np.sum(mask) / total * abs(float(np.mean(y_true[mask])) - float(np.mean(p_up[mask])))
    return float(err)


def _predict_p_up(model, X) -> np.ndarray:
    proba = model.predict_proba(X)
    classes = list(model.classes_)
    p_up = proba[:, classes.index(1)]
    return p_up


def _direction_metrics(y_true: np.ndarray, p_up: np.ndarray, baseline_acc: float) -> dict[str, Any]:
    pred = (p_up >= 0.5).astype(int)
    target_ret = y_true
    y_bin = (target_ret > 0).astype(int)
    strong = (p_up >= 0.60) | (p_up <= 0.40)
    strong_correct = ((p_up >= 0.60) & (target_ret > 0)) | ((p_up <= 0.40) & (target_ret < 0))
    try:
        auc = float(roc_auc_score(y_bin, p_up)) if len(np.unique(y_bin)) == 2 else None
    except Exception:
        auc = None
    acc = float(accuracy_score(y_bin, pred))
    mask = np.abs(target_ret) > 0.003
    if np.any(mask):
        direction_acc_03 = float(np.mean(np.sign(target_ret[mask]) == np.sign(p_up[mask] - 0.5)))
    else:
        direction_acc_03 = None
    return {
        "direction_acc": acc,
        "direction_acc_03": direction_acc_03,
        "auc": auc,
        "brier_score": float(brier_score_loss(y_bin, p_up)),
        "calibration_error": _calibration_error(y_bin, p_up),
        "strong_signal_count": int(np.sum(strong)),
        "strong_signal_ratio": float(np.mean(strong)),
        "strong_signal_win_rate": float(np.mean(strong_correct[strong])) if np.any(strong) else None,
        "direction_baseline_acc": baseline_acc,
        "direction_model_vs_baseline_improvement": float(acc - baseline_acc),
        "score": float(brier_score_loss(y_bin, p_up) - 0.10 * max(acc - baseline_acc, 0)),
    }


def _direction_model(data_train: pd.DataFrame, feature_cols: list[str], progress_cb=None):
    set_log_context(stage="direction_model_train_start")
    logger.info("direction_model_train_start")
    train_base, valid, test = _split_train_valid_test(data_train)
    if progress_cb:
        progress_cb(65, "direction_model_train_start", "Training calibrated direction model")
    y_train = (train_base["target_next"] > 0).astype(int)
    y_valid = (valid["target_next"] > 0).astype(int)
    if y_train.nunique() < 2 or y_valid.nunique() < 2:
        logger.warning("direction_model_skipped_single_class train_classes=%s valid_classes=%s", y_train.nunique(), y_valid.nunique())
        return None, None, [], None, None
    baseline_acc = float(max((test["target_next"] > 0).mean(), (test["target_next"] <= 0).mean()))
    rough = []
    for model_name, selector, scaler, model in _candidates(_classifiers()):
        try:
            base = _make_pipeline(selector, scaler, clone(model), len(feature_cols), "classification")
            base.fit(train_base[feature_cols], y_train)
            calibrated = _calibrated_direction_pipeline(base, valid[feature_cols], y_valid)
            p_valid = _predict_p_up(calibrated, valid[feature_cols])
            m = _direction_metrics(valid["target_next"].to_numpy(), p_valid, baseline_acc)
            rough.append({"model": model_name, "selector": selector, "scaler": scaler, "metrics": m})
        except ProbabilityCalibrationError:
            logger.exception("direction_candidate_calibration_failed model=%s", model_name)
        except Exception:
            logger.exception("direction_candidate_failed model=%s selector=%s scaler=%s", model_name, selector, scaler)
    if not rough:
        logger.error("direction_model_failed no candidates")
        return None, None, [], None, None
    top = sorted(rough, key=lambda x: x["metrics"]["score"])[:5]
    train_valid = pd.concat([train_base, valid])
    calib_size = max(60, int(len(train_valid) * 0.2))
    fit_part = train_valid.iloc[:-calib_size]
    calib_part = train_valid.iloc[-calib_size:]
    y_fit = (fit_part["target_next"] > 0).astype(int)
    y_calib = (calib_part["target_next"] > 0).astype(int)
    final = []
    for item in top:
        if y_fit.nunique() < 2 or y_calib.nunique() < 2:
            logger.warning("direction_final_skipped_single_class")
            continue
        try:
            base = _make_pipeline(item["selector"], item["scaler"], clone(_classifiers()[item["model"]]), len(feature_cols), "classification")
            base.fit(fit_part[feature_cols], y_fit)
            calibrated = _calibrated_direction_pipeline(base, calib_part[feature_cols], y_calib)
            p_test = _predict_p_up(calibrated, test[feature_cols])
            m = _direction_metrics(test["target_next"].to_numpy(), p_test, baseline_acc)
            final.append({**item, "pipeline": calibrated, "p_test": p_test, "final_metrics": m})
        except Exception:
            logger.exception("direction_candidate_failed final model=%s", item["model"])
    if not final:
        logger.error("direction_model_failed final")
        return None, None, [], None, None
    best = sorted(final, key=lambda x: x["final_metrics"]["score"])[0]
    set_log_context(stage="direction_model_train_success")
    logger.info("direction_model_train_success model=%s selector=%s", best["model"], best["selector"])
    # Keep the calibrated model fit on train_valid/calib split; do not refit on all data without calibration holdout.
    selected = _selected_features(best["pipeline"].estimator.estimator, feature_cols)
    return best, best["pipeline"], selected, test, best["p_test"]


def _regime_intervals(test: pd.DataFrame, pred: np.ndarray) -> tuple[dict[str, Any], pd.DataFrame]:
    set_log_context(stage="regime_interval_start")
    logger.info("regime_interval_start")
    try:
        out = test[["date", "target_next"]].copy()
        out["pred"] = pred
        out["residual"] = out["target_next"] - out["pred"]
        vol_col = "residual_vol_60" if "residual_vol_60" in test.columns else "fund_ret_std_20"
        vol = test[vol_col]
        q33, q66 = vol.quantile([0.33, 0.66])
        regimes = pd.Series("mid_vol", index=test.index)
        regimes[vol <= q33] = "low_vol"
        regimes[vol >= q66] = "high_vol"
        out["volatility_regime"] = regimes.values
        abs_resid = out["residual"].abs()
        global_q = {str(q): float(np.quantile(abs_resid, q / 100)) for q in [70, 80, 90, 99]}
        group_q = {}
        group_size = {}
        for group in ["low_vol", "mid_vol", "high_vol"]:
            vals = abs_resid[out["volatility_regime"] == group]
            group_size[group] = int(len(vals))
            if len(vals) >= 50:
                group_q[group] = {str(q): float(np.quantile(vals, q / 100)) for q in [70, 80, 90, 99]}
        coverage = {}
        for q in [70, 80, 90, 99]:
            radius = global_q[str(q)]
            coverage[f"coverage_{q}"] = float(np.mean((out["target_next"] >= out["pred"] - radius) & (out["target_next"] <= out["pred"] + radius)))
        config = {
            "interval_method": "regime_residual_quantile",
            "vol_col": vol_col,
            "regime_thresholds": {"low_max": float(q33), "high_min": float(q66)},
            "global_quantiles": global_q,
            "group_quantiles": group_q,
            "group_size": group_size,
            **coverage,
            "width_70_bp": 2 * global_q["70"] * 10000,
            "width_80_bp": 2 * global_q["80"] * 10000,
            "width_90_bp": 2 * global_q["90"] * 10000,
            "width_99_bp": 2 * global_q["99"] * 10000,
        }
        set_log_context(stage="regime_interval_success")
        logger.info("regime_interval_success")
        return config, out
    except Exception as exc:
        logger.exception("regime_interval_failed")
        raise RegimeIntervalError("Regime interval failed", details={"reason": str(exc)}) from exc


def select_and_train(data_train: pd.DataFrame, progress_cb=None) -> tuple[ModelBundle, dict, pd.DataFrame, pd.DataFrame]:
    try:
        feature_cols = model_feature_columns(data_train)
        if len(feature_cols) == 0:
            raise ModelSelectionError("No model features are available")
        point_best, point_pipeline, selected_point, test, baselines = _point_model(data_train, feature_cols, progress_cb)
        proxy_eval = _proxy_gain_eval(data_train, feature_cols, point_best, test, baselines)
        direction_best, direction_pipeline, selected_direction, direction_test, p_test = _direction_model(data_train, feature_cols, progress_cb)
        interval_config, backtest = _regime_intervals(test, point_best["pred"])
        backtest["zero_baseline"] = 0.0
        backtest["rolling_mean_baseline"] = baselines["rolling_mean"].to_numpy()
        backtest["rolling_median_baseline"] = baselines["rolling_median"].to_numpy()
        backtest["last_ret_baseline"] = baselines["last_ret"].to_numpy()
        backtest["abs_error"] = (backtest["target_next"] - backtest["pred"]).abs()

        direction_backtest = test[["date", "target_next"]].copy()
        direction_metrics = {
            "direction_available": False,
            "direction_failure_reason": "No calibrated direction model was selected",
        }
        direction_model_name = None
        if direction_best is not None and p_test is not None:
            set_log_context(stage="strong_signal_eval_start")
            logger.info("strong_signal_eval_start")
            direction_model_name = direction_best["model"]
            direction_backtest["p_up"] = p_test
            direction_backtest["p_down"] = 1 - direction_backtest["p_up"]
            direction_backtest["direction_signal"] = np.select(
                [p_test >= 0.65, p_test >= 0.60, p_test <= 0.35, p_test <= 0.40],
                ["bullish", "bullish", "bearish", "bearish"],
                default="neutral",
            )
            direction_backtest["direction_strength"] = np.select(
                [p_test >= 0.65, p_test >= 0.60, p_test <= 0.35, p_test <= 0.40],
                ["strong", "weak", "strong", "weak"],
                default="none",
            )
            direction_backtest["strong_signal"] = (p_test >= 0.60) | (p_test <= 0.40)
            direction_backtest["direction_correct"] = ((p_test >= 0.60) & (direction_backtest["target_next"] > 0)) | ((p_test <= 0.40) & (direction_backtest["target_next"] < 0))
            direction_metrics = {**direction_best["final_metrics"], "direction_available": True}
            backtest = backtest.merge(direction_backtest[["date", "p_up", "p_down", "strong_signal"]], on="date", how="left")
            set_log_context(stage="strong_signal_eval_success")
            logger.info("strong_signal_eval_success count=%s", direction_metrics.get("strong_signal_count"))
        else:
            direction_backtest["p_up"] = np.nan
            direction_backtest["p_down"] = np.nan
            direction_backtest["direction_signal"] = "unavailable"
            direction_backtest["direction_strength"] = "none"
            direction_backtest["strong_signal"] = False
            direction_backtest["direction_correct"] = np.nan
            backtest["p_up"] = np.nan
            backtest["p_down"] = np.nan
            backtest["strong_signal"] = False

        y = test["target_next"].to_numpy()
        baseline_median_rmse = float(np.sqrt(mean_squared_error(y, baselines["rolling_median"].to_numpy()))) * 10000
        baseline_last_rmse = float(np.sqrt(mean_squared_error(y, baselines["last_ret"].to_numpy()))) * 10000
        point_metrics = {
            **point_best["final_metrics"],
            "baseline_median_rmse_bp": baseline_median_rmse,
            "baseline_last_rmse_bp": baseline_last_rmse,
            "before_proxy_metrics": proxy_eval.get("before_proxy_metrics"),
            "after_proxy_metrics": proxy_eval.get("after_proxy_metrics"),
            "proxy_feature_gain": proxy_eval.get("proxy_feature_gain"),
            "proxy_features_helpful": proxy_eval.get("proxy_features_helpful"),
            "proxy_feature_count": proxy_eval.get("proxy_feature_count"),
        }
        interval_metrics = {
            "coverage_70": interval_config["coverage_70"],
            "coverage_80": interval_config["coverage_80"],
            "coverage_90": interval_config["coverage_90"],
            "coverage_99": interval_config["coverage_99"],
            "width_70_bp": interval_config["width_70_bp"],
            "width_80_bp": interval_config["width_80_bp"],
            "width_90_bp": interval_config["width_90_bp"],
            "width_99_bp": interval_config["width_99_bp"],
            "residual_group_used": None,
        }
        metrics = {
            "prediction_mode": PREDICTION_MODE,
            "point": point_metrics,
            "direction": direction_metrics,
            "interval": interval_metrics,
            # Backward-compatible flat keys used by existing UI paths.
            **point_metrics,
            **direction_metrics,
            **interval_metrics,
            "final_score": point_metrics["score"],
            "residual_q70": interval_config["global_quantiles"]["70"],
            "residual_q80": interval_config["global_quantiles"]["80"],
            "residual_q90": interval_config["global_quantiles"]["90"],
            "residual_q99": interval_config["global_quantiles"]["99"],
            "before_proxy_metrics": proxy_eval.get("before_proxy_metrics"),
            "after_proxy_metrics": proxy_eval.get("after_proxy_metrics"),
            "proxy_feature_gain": proxy_eval.get("proxy_feature_gain"),
            "proxy_features_helpful": proxy_eval.get("proxy_features_helpful"),
        }
        bundle = ModelBundle(
            point_model_name=point_best["model"],
            direction_model_name=direction_model_name,
            point_pipeline=point_pipeline,
            direction_pipeline=direction_pipeline,
            selected_features_point=selected_point,
            selected_features_direction=selected_direction,
            interval_config=interval_config,
        )
        
        # 相对收益模型训练 (V2.6)
        excess_metrics = _train_excess_models(data_train, feature_cols, test, progress_cb)
        metrics["excess"] = excess_metrics
        
        # 暴露稳定性检查 (V2.6)
        exposure_shift = _check_exposure_shift(test)
        metrics["exposure_shift_flag"] = exposure_shift.get("shift_flag", False)
        metrics["exposure_shift_details"] = exposure_shift
        
        return bundle, metrics, backtest, direction_backtest
    except ModelSelectionError:
        raise
    except Exception as exc:
        logger.exception("model_selection_failed")
        raise ModelSelectionError("Model selection failed", details={"reason": str(exc)}) from exc


def _train_excess_models(data_train: pd.DataFrame, feature_cols: list[str], test: pd.DataFrame, progress_cb=None) -> dict[str, Any]:
    """训练相对收益模型 (V2.6)"""
    set_log_context(stage="excess_model_train_start")
    logger.info("excess_model_train_start")
    
    excess_targets = ["target_excess_cyb", "target_excess_kcb50", "target_excess_top10", "target_excess_theme"]
    results = {}
    
    for target in excess_targets:
        if target not in data_train.columns:
            continue
        
        target_name = target.replace("target_", "")
        train_clean = data_train.dropna(subset=[target])
        
        if len(train_clean) < 100:
            logger.warning("excess_model_skipped target=%s reason=insufficient_data rows=%s", target, len(train_clean))
            continue
        
        try:
            # 简单训练一个 Ridge 模型
            pipe = _make_pipeline("all", "standard", Ridge(alpha=1.0), len(feature_cols), "regression")
            pipe.fit(train_clean[feature_cols], train_clean[target])
            
            # 预测
            pred = pipe.predict(test[feature_cols])
            true_vals = test[target].dropna()
            pred_vals = pred[:len(true_vals)]
            
            if len(true_vals) > 10:
                corr = float(np.corrcoef(true_vals, pred_vals)[0, 1]) if np.std(pred_vals) > 0 else 0.0
                rmse = float(np.sqrt(mean_squared_error(true_vals, pred_vals)))
                
                # 方向预测 (跑赢/跑输)
                direction_true = (true_vals > 0).astype(int)
                direction_pred = (pred_vals > 0).astype(int)
                direction_acc = float(accuracy_score(direction_true, direction_pred))
                
                # AUC
                try:
                    auc = float(roc_auc_score(direction_true, pred_vals)) if len(np.unique(direction_true)) == 2 else None
                except Exception:
                    auc = None
                
                results[target_name] = {
                    "excess_corr": corr,
                    "excess_rmse": rmse,
                    "excess_direction_acc": direction_acc,
                    "excess_auc": auc,
                    "outperform_prob": float(np.mean(pred_vals > 0)),
                    "model_available": True,
                }
                logger.info("excess_model_train_success target=%s corr=%s auc=%s", target_name, round(corr, 3), auc)
        except Exception:
            logger.exception("excess_model_train_failed target=%s", target)
    
    set_log_context(stage="excess_model_train_success")
    logger.info("excess_model_train_success models=%s", list(results.keys()))
    return results


def _check_exposure_shift(test: pd.DataFrame) -> dict[str, Any]:
    """检查暴露漂移 (V2.6)"""
    set_log_context(stage="exposure_stability_check_start")
    logger.info("exposure_stability_check_start")
    
    result = {"shift_flag": False, "proxy_r2_decline": None, "tracking_error_rise": None}
    
    if "proxy_r2_60" not in test.columns or "tracking_error_60" not in test.columns:
        return result
    
    try:
        proxy_r2 = test["proxy_r2_60"].dropna()
        tracking_error = test["tracking_error_60"].dropna()
        
        if len(proxy_r2) >= 20:
            recent_r2 = proxy_r2.iloc[-20:].mean()
            earlier_r2 = proxy_r2.iloc[-60:-20].mean() if len(proxy_r2) >= 60 else proxy_r2.iloc[:-20].mean()
            r2_decline = earlier_r2 - recent_r2
            result["proxy_r2_decline"] = float(r2_decline)
            
            if r2_decline > 0.2:
                result["shift_flag"] = True
        
        if len(tracking_error) >= 20:
            recent_te = tracking_error.iloc[-20:].mean()
            earlier_te = tracking_error.iloc[-60:-20].mean() if len(tracking_error) >= 60 else tracking_error.iloc[:-20].mean()
            te_rise = recent_te - earlier_te
            result["tracking_error_rise"] = float(te_rise)
            
            if te_rise > 0.005:
                result["shift_flag"] = True
        
        set_log_context(stage="exposure_stability_check_success")
        logger.info("exposure_stability_check_success shift_flag=%s", result["shift_flag"])
    except Exception:
        logger.exception("exposure_stability_check_failed")
    
    return result


def update_model_monitoring(fund_code: str, prediction: dict, actual_return: float | None = None) -> dict[str, Any]:
    """更新模型监控记录 (V2.6)"""
    import json
    from pathlib import Path
    
    set_log_context(stage="model_monitoring_start")
    logger.info("model_monitoring_start fund_code=%s", fund_code)
    
    monitor_path = Path("models") / fund_code / "t_plus_1_close" / "model_monitoring.json"
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取现有记录
    if monitor_path.exists():
        with open(monitor_path, "r", encoding="utf-8") as f:
            monitoring = json.load(f)
    else:
        monitoring = {"predictions": [], "degradation_flag": False}
    
    # 添加新记录
    record = {
        "date": prediction.get("asof_date"),
        "pred_return": prediction.get("pred_return"),
        "actual_return": actual_return,
        "p_up": prediction.get("p_up"),
        "direction_signal": prediction.get("direction_signal"),
        "proxy_r2_60": prediction.get("proxy_r2_60"),
        "model_vs_mean_improvement": prediction.get("metrics", {}).get("point", {}).get("model_vs_mean_improvement"),
    }
    
    if actual_return is not None:
        record["error"] = actual_return - prediction.get("pred_return", 0)
        record["direction_correct"] = (actual_return > 0 and prediction.get("p_up", 0.5) > 0.5) or (actual_return < 0 and prediction.get("p_up", 0.5) < 0.5)
    
    monitoring["predictions"].append(record)
    
    # 只保留最近 20 次
    monitoring["predictions"] = monitoring["predictions"][-20:]
    
    # 检查模型退化
    recent = monitoring["predictions"][-20:]
    if len(recent) >= 10:
        mean_improvements = [r.get("model_vs_mean_improvement") for r in recent if r.get("model_vs_mean_improvement") is not None]
        direction_corrects = [r.get("direction_correct") for r in recent if r.get("direction_correct") is not None]
        
        avg_improvement = np.mean(mean_improvements) if mean_improvements else 0
        direction_acc = np.mean(direction_corrects) if direction_corrects else 0.5
        
        monitoring["degradation_flag"] = avg_improvement < 0 or direction_acc < 0.5
        monitoring["avg_model_vs_mean_improvement"] = float(avg_improvement)
        monitoring["recent_direction_acc"] = float(direction_acc)
    
    # 保存
    with open(monitor_path, "w", encoding="utf-8") as f:
        json.dump(monitoring, f, indent=2, ensure_ascii=False)
    
    set_log_context(stage="model_monitoring_success")
    logger.info("model_monitoring_success degradation_flag=%s", monitoring.get("degradation_flag"))
    
    return monitoring


def load_model_monitoring(fund_code: str) -> dict[str, Any]:
    """加载模型监控记录 (V2.6)"""
    import json
    from pathlib import Path
    
    monitor_path = Path("models") / fund_code / "t_plus_1_close" / "model_monitoring.json"
    
    if monitor_path.exists():
        with open(monitor_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {"predictions": [], "degradation_flag": False}
