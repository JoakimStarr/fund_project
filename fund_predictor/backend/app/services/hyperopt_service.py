import logging
import time
from typing import Any

import numpy as np

from app.core.logging_config import set_log_context

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_SPACE = {
    "n_estimators": (50, 300),
    "max_depth": (3, 10),
    "learning_rate": (0.01, 0.3),
    "min_samples_leaf": (5, 30),
}

GRID_FALLBACK_SPACE = {
    "n_estimators": [80, 120, 200],
    "max_depth": [3, 5, 7],
    "learning_rate": [0.03, 0.05, 0.1],
    "min_samples_leaf": [10, 20],
}


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """计算RMSE"""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _try_optuna_optimize(X_train: np.ndarray, y_train: np.ndarray,
                         X_valid: np.ndarray, y_valid: np.ndarray,
                         n_trials: int) -> dict[str, Any] | None:
    """
    使用Optuna进行贝叶斯超参搜索。

    搜索空间：
    - n_estimators: 50-300
    - max_depth: 3-10
    - learning_rate: 0.01-0.3
    - min_samples_leaf: 5-30

    目标：验证集RMSE最小化
    """
    try:
        import optuna
        from sklearn.ensemble import GradientBoostingRegressor

        logger.info("hyperopt_using_optuna trials=%s", n_trials)

        def objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", *DEFAULT_SEARCH_SPACE["n_estimators"]),
                "max_depth": trial.suggest_int("max_depth", *DEFAULT_SEARCH_SPACE["max_depth"]),
                "learning_rate": trial.suggest_float("learning_rate", *DEFAULT_SEARCH_SPACE["learning_rate"], log=True),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", *DEFAULT_SEARCH_SPACE["min_samples_leaf"]),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "max_features": trial.suggest_float("max_features", 0.4, 1.0),
            }

            model = GradientBoostingRegressor(**params, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_valid)

            return _rmse(y_valid, y_pred)

        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective, n_trials=n_trials, show_progressbar=False)

        best_params = dict(study.best_params)
        best_value = study.best_value
        logger.info(
            "hyperopt_optuna_complete best_rmse=%.6f trials=%s params=%s",
            best_value, n_trials, best_params,
        )

        return {
            **best_params,
            "_method": "optuna_tpe",
            "_best_validation_rmse": round(best_value, 6),
            "_n_trials_completed": n_trials,
        }
    except ImportError:
        logger.info("hyperopt_optuna_not_installed will_fallback_to_gridsearch")
        return None
    except Exception as e:
        logger.warning("hyperopt_optuna_error error=%s falling_back_to_gridsearch", e)
        return None


def _grid_search_fallback(X_train: np.ndarray, y_train: np.ndarray,
                          X_valid: np.ndarray, y_valid: np.ndarray) -> dict[str, Any]:
    """
    回退方案：使用sklearn的GridSearchCV进行网格搜索。

    当optuna未安装或执行失败时使用此方法。
    """
    try:
        from itertools import product
        from sklearn.ensemble import GradientBoostingRegressor

        logger.info("hyperopt_grid_search_fallback")

        keys = list(GRID_FALLBACK_SPACE.keys())
        value_lists = list(GRID_FALLBACK_SPACE.values())
        all_combinations = list(product(*value_lists))

        best_rmse = float("inf")
        best_params = {}
        total = len(all_combinations)

        for i, combo in enumerate(all_combinations):
            params = dict(zip(keys, combo))
            try:
                model = GradientBoostingRegressor(**params, random_state=42)
                model.fit(X_train, y_train)
                y_pred = model.predict(X_valid)
                rmse_val = _rmse(y_valid, y_pred)

                if rmse_val < best_rmse:
                    best_rmse = rmse_val
                    best_params = dict(params)
            except Exception:
                continue

        logger.info(
            "hyperopt_grid_search_complete best_rmse=%.6s total_combos=%s",
            best_rmse, total,
        )

        return {
            **best_params,
            "_method": "grid_search",
            "_best_validation_rmse": round(best_rmse, 6) if best_rmse != float("inf") else None,
            "_n_trials_completed": total,
        }
    except Exception as e:
        logger.exception("hyperopt_grid_search_failed error=%s", e)
        return {
            "n_estimators": 120,
            "max_depth": 5,
            "learning_rate": 0.05,
            "min_samples_leaf": 15,
            "_method": "default_fallback",
            "_best_validation_rmse": None,
            "_error": str(e),
        }


def optimize_hyperparams(X_train, y_train, X_valid, y_valid, n_trials: int = 50) -> dict:
    """
    超参数优化服务：对LightGBM/XGBoost（此处用GBDT替代）做贝叶斯超参搜索。

    优先使用Optuna TPE采样器，如果optuna未安装则回退到GridSearchCV。
    函数内部用try/except处理import错误和运行时错误。

    搜索空间：
    - n_estimators: 50~300
    - max_depth: 3~10
    - learning_rate: 0.01~0.3
    - min_samples_leaf: 5~30

    目标：验证集 RMSE 最小化

    Args:
        X_train: 训练特征矩阵
        y_train: 训练标签
        X_valid: 验证特征矩阵
        y_valid: 验证标签
        n_trials: Optuna试验次数（默认50）

    Returns:
        最佳参数字典，包含以下字段：
        - n_estimators, max_depth, learning_rate, min_samples_leaf: 超参数值
        - _method: 使用的方法（optuna_tpe / grid_search / default_fallback）
        - _best_validation_rmse: 验证集最佳RMSE
        - _n_trials_completed: 完成的试验/组合数
    """
    set_log_context(stage="hyperopt_start")
    start_time = time.time()
    logger.info(
        "hyperopt_start train_shape=%s valid_shape=%s trials=%s",
        getattr(X_train, 'shape', len(X_train)),
        getattr(X_valid, 'shape', len(X_valid)),
        n_trials,
    )

    try:
        X_train_arr = np.asarray(X_train)
        y_train_arr = np.asarray(y_train).ravel()
        X_valid_arr = np.asarray(X_valid)
        y_valid_arr = np.asarray(y_valid).ravel()

        if len(X_train_arr) == 0 or len(X_valid_arr) == 0:
            raise ValueError("训练集或验证集为空")

        optuna_result = _try_optuna_optimize(
            X_train_arr, y_train_arr, X_valid_arr, y_valid_arr, n_trials
        )

        if optuna_result is not None:
            result = optuna_result
        else:
            result = _grid_search_fallback(
                X_train_arr, y_train_arr, X_valid_arr, y_valid_arr
            )

        elapsed = time.time() - start_time
        result["_elapsed_seconds"] = round(elapsed, 2)

        set_log_context(stage="hyperopt_success")
        logger.info(
            "hyperopt_success method=%s best_rmse=%.6s elapsed=%.2fs params=%s",
            result.get("_method"), result.get("_best_validation_rmse"), elapsed,
            {k: v for k, v in result.items() if not k.startswith("_")},
        )
        return result

    except Exception as e:
        set_log_context(stage="hyperopt_failed")
        logger.exception("hyperopt_failed error=%s", e)
        elapsed = time.time() - start_time
        return {
            "n_estimators": 120,
            "max_depth": 5,
            "learning_rate": 0.05,
            "min_samples_leaf": 15,
            "_method": "error_fallback",
            "_best_validation_rmse": None,
            "_elapsed_seconds": round(elapsed, 2),
            "_error": str(e),
        }
