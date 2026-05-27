import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from app.core.config import MIN_TRAIN_ROWS, MODEL_DIR, PROCESSED_DIR, RAW_DIR
from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)

MIN_DAYS_FOR_COLD_START = 220
GROUP_MODEL_MIN_SAMPLES = 3
INDIVIDUAL_MODEL_THRESHOLD = 400


def should_use_group_model(fund_code: str) -> tuple[bool, int]:
    """
    判断基金是否应使用冷启动群体模型。

    三段式判断逻辑：
    - history_days < 220: 使用群体模型（100%群体预测）
    - 220 <= history_days < 400: 使用群体模型 + 渐变过渡（blend_weight从0到1）
    - history_days >= 400: 切换到个体模型

    Args:
        fund_code: 基金代码

    Returns:
        (是否使用群体模型, 历史天数)
    """
    set_log_context(fund_code=fund_code, stage="cold_start_check")
    try:
        nav_path = RAW_DIR / "fund_nav" / f"{fund_code}.csv"
        if not nav_path.exists():
            logger.info("cold_start_no_nav_file fund_code=%s using_group_model=True", fund_code)
            return True, 0

        import pandas as pd
        df = pd.read_csv(nav_path, parse_dates=["date"])
        history_days = len(df)

        if history_days < INDIVIDUAL_MODEL_THRESHOLD:
            logger.info(
                "cold_start_use_group_model fund_code=%s days=%s threshold=%s using_group_model=True",
                fund_code, history_days, INDIVIDUAL_MODEL_THRESHOLD,
            )
            return True, history_days

        model_dir = MODEL_DIR / fund_code
        has_model = model_dir.exists() and (model_dir / "model.pkl").exists()
        if not has_model:
            logger.info("cold_start_no_model fund_code=%s days=%s using_group_model=True", fund_code, history_days)
            return True, history_days

        logger.info("cold_start_switch_individual fund_code=%s days=%s using_group_model=False", fund_code, history_days)
        return False, history_days
    except Exception as e:
        logger.exception("cold_start_check_error fund_code=%s error=%s", fund_code, e)
        return True, 0


def _get_fund_type_from_profile(fund_code: str) -> str:
    """获取基金类型"""
    try:
        from app.services.fund_profile_service import classify_fund
        profile = classify_fund(fund_code)
        return profile.fund_type or "unknown"
    except Exception:
        return "unknown"


def _get_peer_models(fund_type: str) -> list[tuple[str, Path]]:
    """
    获取同类型基金中所有已训练的模型路径。

    Returns:
        [(基金代码, 模型目录路径), ...]
    """
    peers = []
    if not MODEL_DIR.exists():
        return peers

    for model_dir in MODEL_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        code = model_dir.name
        if code == fund_code:
            continue

        peer_type = _get_fund_type_from_profile(code)
        if peer_type != fund_type:
            continue

        model_file = model_dir / "model.pkl"
        metrics_file = model_dir / "metrics.json"
        if model_file.exists() and metrics_file.exists():
            peers.append((code, model_dir))

    return peers


def _compute_group_baseline(peer_models: list[tuple[str, Path]], features: dict) -> float | None:
    """
    计算同类型基金群体的平均预测值作为基线。

    对每个已训练模型进行推理，取平均。
    """
    predictions = []
    for code, model_dir in peer_models:
        try:
            import joblib
            import pandas as pd

            model = joblib.load(model_dir / "model.pkl")

            selected_features_file = model_dir / "selected_features.json"
            if not selected_features_file.exists():
                continue

            import json
            with open(selected_features_file) as f:
                selected_features = json.load(f)

            feature_vec = np.array([features.get(f, 0.0) for f in selected_features]).reshape(1, -1)
            pred = float(model.predict(feature_vec)[0])
            predictions.append(pred)
        except Exception as e:
            logger.warning("cold_start_peer_prediction_failed fund_code=%s error=%s", code, e)
            continue

    if len(predictions) < GROUP_MODEL_MIN_SAMPLES:
        logger.warning(
            "cold_start_insufficient_peers peer_count=%s needed=%s",
            len(predictions), GROUP_MODEL_MIN_SAMPLES,
        )
        return None

    baseline = float(np.mean(predictions))
    logger.info("cold_start_group_baseline computed peers=%s baseline=%.6f", len(predictions), baseline)
    return baseline


def _compute_fine_tuning_adjustment(fund_code: str, features: dict, group_baseline: float) -> float:
    """
    微调修正：基于目标基金已有的有限历史数据对群体基线做偏移修正。

    使用最近可用的收益数据计算与群体均值的偏差趋势，
    在3-6个月期间逐步从纯群体模型过渡到个体模型。
    """
    set_log_context(fund_code=fund_code, stage="cold_start_fine_tuning")
    adjustment = 0.0

    try:
        nav_path = RAW_DIR / "fund_nav" / f"{fund_code}.csv"
        if not nav_path.exists():
            return adjustment

        import pandas as pd
        df = pd.read_csv(nav_path, parse_dates=["date"])
        history_days = len(df)

        if history_days < 30:
            logger.info("cold_start_fine_tuning_skip too_short days=%s", history_days)
            return adjustment

        recent_ret = df["daily_growth_pct"].tail(min(30, history_days)).astype(float).mean() / 100.0

        if history_days < MIN_DAYS_FOR_COLD_START:
            blend_weight = 0.0
        elif history_days < INDIVIDUAL_MODEL_THRESHOLD:
            blend_weight = (history_days - MIN_DAYS_FOR_COLD_START) / (INDIVIDUAL_MODEL_THRESHOLD - MIN_DAYS_FOR_COLD_START)
        else:
            blend_weight = 1.0
        blend_weight = max(0.0, min(1.0, blend_weight))
        adjustment = recent_ret * (1.0 - blend_weight) * 0.5

        logger.info(
            "cold_start_fine_tuning fund_code=%s days=%s recent_mean_ret=%.6f adjustment=%.6f blend=%.2f",
            fund_code, history_days, recent_ret, adjustment, blend_weight,
        )
    except Exception as e:
        logger.warning("cold_start_fine_tuning_failed error=%s", e)

    return adjustment


def get_group_model_prediction(fund_code: str, fund_type: str, features: dict) -> float:
    """
    冷启动群体模型预测。

    当基金历史不足120天时使用同类基金的群体模型：
    - 按fund_type分组，用同类型所有已训练模型的平均预测作为基线
    - 3-6个月期间：群体模型 + 微调修正（基于已有有限数据的偏差调整）
    - 超过6个月后逐步过渡到个体模型

    Args:
        fund_code: 目标基金代码
        fund_type: 基金类型（equity_active/hybrid_equity/index_equity等）
        features: 特征字典 {特征名: 特征值}

    Returns:
        预测值（float），如果无法计算则返回0.0
    """
    set_log_context(fund_code=fund_code, stage="group_model_predict_start")
    logger.info(
        "group_model_predict_start fund_code=%s fund_type=%s feature_count=%s",
        fund_code, fund_type, len(features),
    )

    try:
        use_group, history_days = should_use_group_model(fund_code)
        if not use_group:
            logger.info("cold_start_skipped fund_code=%s has_sufficient_history", fund_code)
            return 0.0

        resolved_type = fund_type or _get_fund_type_from_profile(fund_code)
        peer_models = _get_peer_models(resolved_type)

        if not peer_models:
            logger.warning("cold_start_no_peers fund_code=%s type=%s", fund_code, resolved_type)
            return 0.0

        group_baseline = _compute_group_baseline(peer_models, features)
        if group_baseline is None:
            logger.warning("cold_start_baseline_none fund_code=%s", fund_code)
            return 0.0

        fine_tune_adj = _compute_fine_tuning_adjustment(fund_code, features, group_baseline)

        if history_days < MIN_DAYS_FOR_COLD_START:
            blend_weight = 0.0
        elif history_days < INDIVIDUAL_MODEL_THRESHOLD:
            blend_weight = (history_days - MIN_DAYS_FOR_COLD_START) / (INDIVIDUAL_MODEL_THRESHOLD - MIN_DAYS_FOR_COLD_START)
        else:
            blend_weight = 1.0
        blend_weight = max(0.0, min(1.0, blend_weight))
        final_pred = group_baseline * (1.0 - blend_weight * 0.5) + fine_tune_adj

        logger.info(
            "group_model_predict_success fund_code=%s baseline=%.6f adj=%.6f final=%.6f blend=%.2f peers=%s days=%s",
            fund_code, group_baseline, fine_tune_adj, final_pred, blend_weight, len(peer_models), history_days,
        )

        set_log_context(stage="group_model_predict_success")
        return float(final_pred)
    except Exception as e:
        set_log_context(stage="group_model_predict_failed")
        logger.exception("group_model_predict_failed fund_code=%s error=%s", fund_code, e)
        return 0.0
