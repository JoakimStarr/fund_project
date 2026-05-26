import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import async_session
from app.models.prediction import Prediction
from app.models.fund_nav import FundNav
from app.models.fund_profile import FundProfileCache
from app.schemas.predict import PredictResponse, ConfidenceInterval, ModelInfo, ConstraintInfo, FundHealth, ShapFactor
from app.services.features.feature_service import build_features
from app.services.model.versioning import load_model
from app.services.model.conformal import predict_interval
from app.services.model.constraints import apply_constraints
from app.services.model.cold_start import should_use_group_model
from app.services.predict.shap_service import explain
from app.services.fund.profile_service import get_profile as get_fund_profile


async def predict(fund_code: str, session, force_retrain: bool = False) -> PredictResponse:
    profile = await get_fund_profile(fund_code)
    fund_type = profile.get("fund_type", "hybrid_equity")
    fund_name = profile.get("fund_name", "")
    nav_result = await session.execute(
        select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
    )
    nav_rows = nav_result.scalars().all()
    if not nav_rows:
        raise ValueError(f"基金 {fund_code} 无净值数据")
    nav_df = pd.DataFrame([{"nav_date": r.nav_date, "nav": r.nav, "acc_nav": r.acc_nav} for r in nav_rows])
    n_days = len(nav_df)
    today = datetime.now().strftime("%Y-%m-%d")
    target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    cold_start_info = should_use_group_model(fund_code, n_days)
    model_data, metrics, features_list = load_model(fund_code)
    if cold_start_info["use_group"] or model_data is None:
        predicted_return = 0.0
        lower = -0.02
        upper = 0.02
        direction = "neutral"
        direction_prob = 0.50
        confidence = "low"
        clipped_return, is_clipped, limit = apply_constraints(fund_type, predicted_return)
        constraint_info = ConstraintInfo(is_clipped=is_clipped, original_return=predicted_return if is_clipped else None, limit=limit if is_clipped else None)
        model_info = None
        shap_factors = None
        prev_nav_val = float(nav_rows[-1].nav) if nav_rows else None
        predicted_nav_val = float(prev_nav_val * (1 + clipped_return)) if prev_nav_val else None
        data_days = n_days
        data_sufficiency = "insufficient" if data_days < 250 else "sufficient"
        data_freshness = "fresh"
        latest_nav_date = str(nav_rows[-1].nav_date) if nav_rows else ""
        health = FundHealth(data_sufficiency=data_sufficiency, data_days=data_days, data_freshness=data_freshness, latest_nav_date=latest_nav_date, prediction_reliability=confidence, warnings=["冷启动模式：历史数据不足或模型不存在"])
        return PredictResponse(fund_code=fund_code, fund_name=fund_name, fund_type=fund_type, predict_date=today, target_date=target_date, predicted_return=float(clipped_return), predicted_nav=predicted_nav_val, prev_nav=prev_nav_val, confidence_interval=ConfidenceInterval(lower=float(lower), upper=float(upper), confidence_level=0.90), direction=direction, direction_probability=direction_prob, confidence=confidence, constraint_info=constraint_info, fund_health=health)
    model = model_data["model"]
    scaler = model_data.get("scaler")
    calibration = model_data.get("calibration")
    latest_nav = nav_rows[-1]
    prev_nav_val = float(latest_nav.nav)
    features_df = build_features(fund_code, nav_df.to_dict("records"), fund_type)
    if features_df.empty:
        raise ValueError("特征构建失败")
    latest_features = features_df.iloc[-1:].fillna(0)
    if scaler is not None:
        X = scaler.transform(latest_features.values)
    else:
        X = latest_features.values
    pred, lower_arr, upper_arr = predict_interval(model, X, calibration)
    predicted_return = float(pred[0])
    lower = float(lower_arr[0])
    upper = float(upper_arr[0])
    clipped_return, is_clipped, limit = apply_constraints(fund_type, predicted_return)
    direction = "up" if clipped_return > 0 else "down" if clipped_return < 0 else "neutral"
    direction_prob = min(0.95, max(0.05, 0.5 + abs(clipped_return) * 10))
    confidence = "high" if abs(clipped_return) > 0.01 else "medium"
    constraint_info = ConstraintInfo(is_clipped=is_clipped, original_return=predicted_return if is_clipped else None, limit=limit if is_clipped else None)
    shap_factors = explain(model, X, features_df.columns.tolist())
    model_type_str = metrics.get("best_model", "unknown") if metrics else "unknown"
    model_info = ModelInfo(model_type=model_type_str, mae=metrics.get("valid_mae") if metrics else None, direction_accuracy=metrics.get("valid_direction_accuracy") if metrics else None, features_used=metrics.get("features_used") if metrics else X.shape[1], trained_date=metrics.get("model_version") if metrics else None, model_version=metrics.get("model_version") if metrics else None, wfcv_rounds=metrics.get("wfcv_rounds") if metrics else None)
    predicted_nav_val = float(prev_nav_val * (1 + clipped_return))
    data_days = n_days
    data_sufficiency = "sufficient"
    data_freshness = "fresh"
    latest_nav_date = str(latest_nav.nav_date)
    health = FundHealth(data_sufficiency=data_sufficiency, data_days=data_days, data_freshness=data_freshness, latest_nav_date=latest_nav_date, prediction_reliability=confidence)
    new_pred = Prediction(fund_code=fund_code, predict_date=today, target_date=target_date, predicted_return=clipped_return, lower_bound=lower, upper_bound=upper, direction=direction, direction_prob=direction_prob, confidence_level=0.90, model_type=model_type_str, model_version=metrics.get("model_version") if metrics else None, features_used=X.shape[1], fund_type=fund_type)
    session.add(new_pred)
    await session.flush()
    return PredictResponse(fund_code=fund_code, fund_name=fund_name, fund_type=fund_type, predict_date=today, target_date=target_date, predicted_return=float(clipped_return), predicted_nav=predicted_nav_val, prev_nav=prev_nav_val, confidence_interval=ConfidenceInterval(lower=float(lower), upper=float(upper), confidence_level=0.90), direction=direction, direction_probability=direction_prob, confidence=confidence, model_info=model_info, constraint_info=constraint_info, shap_top_factors=shap_factors, fund_health=health)