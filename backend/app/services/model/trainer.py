import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from app.core.config import settings
from app.core.database import engine, async_session
from app.models.fund_nav import FundNav
from app.models.fund_profile import FundProfileCache
from app.services.features.feature_service import build_and_screen
from app.services.model.walk_forward import calc_wfcv_params, run_wfcv
from app.services.model.ensemble import StackingModel
from app.services.model.conformal import calibrate
from app.services.model.versioning import save_model


def _do_sync_training(nav_data_list: list, fund_type: str, features, selected_features, fund_code, use_simplified_mode: bool = False) -> dict:
    import pandas as pd
    nav_df = pd.DataFrame(nav_data_list)
    nav_df["nav_date"] = pd.to_datetime(nav_df["nav_date"])
    nav_df = nav_df.sort_values("nav_date").set_index("nav_date")
    forward_returns = nav_df["nav"].pct_change().shift(-1)
    aligned = features.align(forward_returns, join="inner", axis=0)
    X_df, y_series = aligned[0], aligned[1]
    X_df = X_df[selected_features] if selected_features else X_df
    X = X_df.values.astype(np.float64)
    y = y_series.values.astype(np.float64)
    mask = ~(np.isnan(y) | np.isinf(y))
    X, y = X[mask], y[mask]
    nan_mask = ~np.any(np.isnan(X) | np.isinf(X), axis=1)
    X, y = X[nan_mask], y[nan_mask]
    n_total = len(X)
    
    # 简化模式：针对新成立基金，降低数据量要求
    MIN_ROWS_FULL = 150
    MIN_ROWS_SIMPLIFIED = 60
    
    if n_total < MIN_ROWS_SIMPLIFIED:
        raise ValueError(f"清洗后数据仅 {n_total} 行，无法训练（至少需要{MIN_ROWS_SIMPLIFIED}行）")
    
    # 自动切换到简化模式
    if n_total < MIN_ROWS_FULL and not use_simplified_mode:
        use_simplified_mode = True
        print(f"[简化模式] 基金 {fund_code} 数据量 {n_total} 行，启用简化训练模式")
    wfcv_params = calc_wfcv_params(n_total, use_simplified_mode)
    splits = settings.model["train_split_ratio"]
    train_end = int(n_total * splits[0])
    valid_end = train_end + int(n_total * splits[1])
    test_select_end = valid_end + int(n_total * splits[2])
    X_train, y_train = X[:train_end], y[:train_end]
    X_valid, y_valid = X[train_end:valid_end], y[train_end:valid_end]
    X_test_select, y_test_select = X[valid_end:test_select_end], y[valid_end:test_select_end]
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_valid_s = scaler.transform(X_valid)
    X_test_select_s = scaler.transform(X_test_select)
    candidate_configs = settings.model["candidate_models"]
    models = {}
    
    # 简化模式：只使用简单模型，禁用复杂集成学习
    if use_simplified_mode:
        # 简化模式：只使用线性模型，避免过拟合
        candidate_configs = [
            {"name": "ridge", "alpha": 1.0},
            {"name": "elasticnet", "alpha": 0.01, "l1_ratio": 0.5}
        ]
        print(f"[简化模式] 使用简化模型配置: {[c['name'] for c in candidate_configs]}")
    
    # 根据训练数据量动态调整超参数
    n_train = len(X_train)
    if n_train < 100 or use_simplified_mode:
        # 小数据集或简化模式：保守配置，防止过拟合
        lgbm_n_estimators, lgbm_max_depth, lgbm_min_child = 20, 2, 20
        xgb_n_estimators, xgb_max_depth, xgb_min_child = 15, 2, 10
    elif n_train < 300:
        # 中等数据集
        lgbm_n_estimators, lgbm_max_depth, lgbm_min_child = 60, 4, 12
        xgb_n_estimators, xgb_max_depth, xgb_min_child = 40, 4, 3
    elif n_train < 600:
        # 较大数据集
        lgbm_n_estimators, lgbm_max_depth, lgbm_min_child = 80, 5, 10
        xgb_n_estimators, xgb_max_depth, xgb_min_child = 60, 5, 2
    else:
        # 大数据集：使用配置文件的默认值
        lgbm_n_estimators, lgbm_max_depth, lgbm_min_child = 120, 6, 8
        xgb_n_estimators, xgb_max_depth, xgb_min_child = 100, 6, 2
    
    for cfg in candidate_configs:
        name = cfg["name"]
        if name == "ridge":
            models[name] = Ridge(alpha=cfg.get("alpha", 1.0))
        elif name == "elasticnet":
            models[name] = ElasticNet(alpha=cfg.get("alpha", 0.01), l1_ratio=cfg.get("l1_ratio", 0.5), max_iter=1000)
        elif name == "lgbm":
            from lightgbm import LGBMRegressor
            # 使用 dart boosting 增加多样性，防止过拟合
            models[name] = LGBMRegressor(
                boosting_type=cfg.get("boosting_type", "dart"),
                n_estimators=cfg.get("n_estimators", lgbm_n_estimators),
                max_depth=cfg.get("max_depth", lgbm_max_depth),
                learning_rate=cfg.get("learning_rate", 0.05),
                min_child_samples=cfg.get("min_child_samples", lgbm_min_child),
                drop_rate=cfg.get("drop_rate", 0.1),
                skip_drop=cfg.get("skip_drop", 0.5),
                verbose=-1
            )
        elif name == "xgboost":
            from xgboost import XGBRegressor
            # 传统 gbdt，与 LGBM 形成方法论差异
            models[name] = XGBRegressor(
                booster=cfg.get("booster", "gbtree"),
                n_estimators=cfg.get("n_estimators", xgb_n_estimators),
                max_depth=cfg.get("max_depth", xgb_max_depth),
                learning_rate=cfg.get("learning_rate", 0.08),
                min_child_weight=cfg.get("min_child_weight", xgb_min_child),
                subsample=cfg.get("subsample", 0.8),
                colsample_bytree=cfg.get("colsample_bytree", 0.8),
                verbosity=0
            )
    # 简化模式：禁用堆叠模型
    if not use_simplified_mode:
        stacking = StackingModel()
        models["stacking"] = stacking
    
    results = {}
    best_score = float("inf")
    best_model = None
    best_name = ""
    for name, model in models.items():
        model.fit(X_train_s, y_train)
        pred = model.predict(X_valid_s)
        mae = float(np.mean(np.abs(pred - y_valid)))
        # 计算 MSE 和 RMSE
        mse = float(np.mean((pred - y_valid) ** 2))
        rmse = float(np.sqrt(mse))
        direction_acc = float(np.mean((pred > 0) == (y_valid > 0)))
        mae_weight = settings.model["selection_mae_weight"]
        dir_weight = settings.model["selection_direction_weight"]
        score = mae * mae_weight + (1 - direction_acc) * dir_weight
        results[name] = {"mae": mae, "mse": mse, "rmse": rmse, "direction_accuracy": direction_acc, "score": score}
        if score < best_score:
            best_score = score
            best_model = model
            best_name = name
    
    # 简化模式：跳过WFCV或使用简化版本
    if use_simplified_mode:
        wfcv_results = [{"round": 0, "mae": results[best_name]["mae"], "direction_accuracy": results[best_name]["direction_accuracy"]}]
        print(f"[简化模式] 跳过WFCV交叉验证")
    elif wfcv_params["actual_rounds"] >= 3:
        wfcv_results = run_wfcv(Ridge, {"alpha": 1.0}, StandardScaler().fit_transform(X), y, wfcv_params)
    else:
        wfcv_results = [{"round": 0, "mae": results[best_name]["mae"], "direction_accuracy": results[best_name]["direction_accuracy"]}]
    calib_result = calibrate(best_model, X_test_select_s, y_test_select)
    full_X = np.vstack([X_train_s, X_valid_s])
    full_y = np.hstack([y_train, y_valid])
    best_model.fit(full_X, full_y)
    from datetime import datetime
    trained_date = datetime.now().strftime("%Y%m%d")
    metrics = {
        "best_model": best_name,
        "valid_mae": results[best_name]["mae"],
        "valid_mse": results[best_name]["mse"],
        "valid_rmse": results[best_name]["rmse"],
        "valid_direction_accuracy": results[best_name]["direction_accuracy"],
        "valid_score": best_score,
        "wfcv_rounds": wfcv_params["actual_rounds"],
        "wfcv_degraded": wfcv_params["degraded"],
        "wfcv_mean_mae": float(np.mean([r["mae"] for r in wfcv_results])),
        "wfcv_mean_direction_acc": float(np.mean([r["direction_accuracy"] for r in wfcv_results])),
        "features_used": X.shape[1],
        "features_selected": len(selected_features) if selected_features else X.shape[1],
        "train_rows": n_total,
        "calibration_q_value": calib_result["q_value"],
        "calibration_size": calib_result["calibration_size"],
        "trained_date": trained_date,
        "simplified_mode": use_simplified_mode,
    }
    model_version = trained_date
    metrics["model_version"] = model_version
    save_model(fund_code, {"model": best_model, "scaler": scaler, "calibration": calib_result, "fund_type": fund_type}, metrics, selected_features if selected_features else [])
    return metrics


async def train_model(fund_code: str, session) -> dict:
    result = await session.execute(
        select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
    )
    nav_rows = result.scalars().all()
    # 简化模式：允许最少60行原始数据
    min_rows = 60
    if not nav_rows or len(nav_rows) < min_rows:
        raise ValueError(f"基金 {fund_code} NAV数据不足 {min_rows} 行，当前 {len(nav_rows)} 行")
    profile_result = await session.execute(
        select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
    )
    profile = profile_result.scalar_one_or_none()
    fund_type = profile.fund_type if profile else "hybrid_equity"
    nav_data_list = [{"nav_date": r.nav_date, "nav": r.nav, "acc_nav": r.acc_nav, "daily_return": r.daily_return} for r in nav_rows]
    features, selected_features = build_and_screen(fund_code, nav_data_list, fund_type)
    # 根据数据量决定是否使用简化模式
    use_simplified = len(nav_data_list) < 300
    return _do_sync_training(nav_data_list, fund_type, features, selected_features, fund_code, use_simplified_mode=use_simplified)