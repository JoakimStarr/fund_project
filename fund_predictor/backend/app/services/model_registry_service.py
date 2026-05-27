import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.config import MODEL_DIR
from app.core.errors import ModelNotFoundError
from app.services.model_selection_service import PREDICTION_MODE

logger = logging.getLogger(__name__)


def fund_model_dir(fund_code: str) -> Path:
    return MODEL_DIR / fund_code / PREDICTION_MODE


def model_exists(fund_code: str) -> bool:
    return (fund_model_dir(fund_code) / "point_model.pkl").exists()


def save_model_archive(
    fund_code: str,
    bundle,
    config: dict[str, Any],
    metrics: dict[str, Any],
    backtest: pd.DataFrame,
    direction_backtest: pd.DataFrame,
) -> None:
    path = fund_model_dir(fund_code)
    path.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle.point_pipeline, path / "point_model.pkl")
    if bundle.direction_pipeline is not None:
        joblib.dump(bundle.direction_pipeline, path / "direction_model.pkl")
    (path / "interval_config.json").write_text(json.dumps(bundle.interval_config, ensure_ascii=False, indent=2), encoding="utf-8")
    normalized_config = {
        "fund_code": fund_code,
        "prediction_mode": PREDICTION_MODE,
        "point_model_name": bundle.point_model_name,
        "direction_model_name": bundle.direction_model_name,
        "interval_method": bundle.interval_config.get("interval_method"),
        "selected_features_point": bundle.selected_features_point,
        "selected_features_direction": bundle.selected_features_direction,
        "train_window": config.get("train_window", 180),
        "last_train_date": config["last_train_date"],
        "feature_count_point": len(bundle.selected_features_point),
        "feature_count_direction": len(bundle.selected_features_direction),
        "data_start_date": config["data_start_date"],
        "data_end_date": config["data_end_date"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (path / "config.json").write_text(json.dumps(normalized_config, ensure_ascii=False, indent=2), encoding="utf-8")
    (path / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (path / "selected_features.json").write_text(
        json.dumps({"point": bundle.selected_features_point, "direction": bundle.selected_features_direction}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    backtest.to_csv(path / "backtest.csv", index=False, encoding="utf-8")
    direction_backtest.to_csv(path / "direction_backtest.csv", index=False, encoding="utf-8")
    history_path = path / "prediction_history.csv"
    if not history_path.exists():
        pd.DataFrame(
            columns=[
                "created_at",
                "asof_date",
                "prediction_mode",
                "pred_return",
                "p_up",
                "p_down",
                "direction_signal",
                "direction_strength",
                "actual",
                "abs_error",
                "direction_correct",
                "strong_signal",
                "covered_80",
                "covered_90",
                "point_model_name",
                "direction_model_name",
                "interval_method",
                "flat_prediction",
                "pred_real_std_ratio",
                "pred_real_corr",
                "model_vs_mean_improvement",
                "strong_signal_win_rate",
                "residual_group_used",
                "residual_group_fallback",
                "today_nav",
                "pred_nav",
                "lower_nav_80",
                "upper_nav_80",
                "lower_nav_90",
                "upper_nav_90",
                "proxy_r2_60",
                "tracking_error_60",
                "proxy_quality_flag",
                "proxy_features_helpful",
                "holding_report_date",
                "holding_scope",
                "top10_proxy_available_count",
                "top10_proxy_missing_count",
                "theme_available_count",
                "lower_70",
                "upper_70",
                "lower_80",
                "upper_80",
                "lower_90",
                "upper_90",
                "lower_99",
                "upper_99",
            ]
        ).to_csv(history_path, index=False)


def load_model_archive(fund_code: str) -> tuple[Any, Any | None, dict, dict, dict]:
    path = fund_model_dir(fund_code)
    if not (path / "point_model.pkl").exists():
        raise ModelNotFoundError("该基金尚未训练，请点击训练并预测", details={"fund_code": fund_code, "prediction_mode": PREDICTION_MODE})
    point_model = joblib.load(path / "point_model.pkl")
    direction_model = None
    direction_model_error = None
    direction_path = path / "direction_model.pkl"
    if direction_path.exists():
        try:
            direction_model = joblib.load(direction_path)
        except Exception as exc:
            direction_model_error = str(exc)
            logger.warning("direction_model_load_failed fund_code=%s reason=%s", fund_code, direction_model_error)
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    interval_config = json.loads((path / "interval_config.json").read_text(encoding="utf-8"))
    if direction_model_error:
        config["direction_model_load_error"] = direction_model_error
        metrics["direction_model_load_error"] = direction_model_error
    return point_model, direction_model, config, metrics, interval_config


def get_model_info(fund_code: str) -> dict[str, Any]:
    path = fund_model_dir(fund_code)
    if not path.exists():
        raise ModelNotFoundError("模型档案不存在", details={"fund_code": fund_code, "prediction_mode": PREDICTION_MODE})
    _, _, config, metrics, interval_config = load_model_archive(fund_code)
    selected = json.loads((path / "selected_features.json").read_text(encoding="utf-8"))
    return {"config": config, "metrics": metrics, "interval_config": interval_config, "selected_features": selected}


def append_prediction(fund_code: str, row: dict[str, Any]) -> None:
    path = fund_model_dir(fund_code) / "prediction_history.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    out = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
    out.to_csv(path, index=False, encoding="utf-8")


def should_retrain(fund_code: str, force_retrain: bool = False) -> bool:
    return bool(force_retrain or not model_exists(fund_code))
