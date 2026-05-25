"""
模型集成层：Stacking Ridge 元学习器。

策略方案 §7.2 第一层→第二层实现：
- Layer1: 多基础模型输出
- Layer2: Ridge回归线性组合各模型优势区间
- Layer3: 残差自适应修正
"""
import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)


class StackingEnsemble:
    """两层Stacking集成模型
    
    用法：
    1. fit_base_models(): 训练第一层各基础模型
    2. fit_meta_learner(): 在验证集上训练Ridge元学习器
    3. predict(): 输出集成预测结果
    """
    
    def __init__(self, alpha: float = 1.0):
        self.base_models: dict[str, Any] = {}
        self.meta_learner: Optional[Ridge] = None
        self.alpha = alpha
        self.fitted = False
        self.meta_feature_names: list[str] = []
    
    def add_base_model(self, name: str, model: Any) -> None:
        self.base_models[name] = model
    
    def fit_meta_learner(
        self,
        X_valid: pd.DataFrame,
        y_valid: np.ndarray | pd.Series,
        feature_cols: list[str],
    ) -> dict[str, Any]:
        """用验证集上各模型的预测作为特征，训练Ridge元学习器
        
        Returns:
            训练指标字典
        """
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        
        meta_features = {}
        for name, model in self.base_models.items():
            try:
                cols = [c for c in feature_cols if c in X_valid.columns]
                pred = model.predict(X_valid[cols])
                meta_features[name] = pred
                
                mae = mean_absolute_error(y_valid, pred)
                rmse = np.sqrt(mean_squared_error(y_valid, pred))
                logger.info(
                    "stacking_base_model name=%s valid_mae=%.6f valid_rmse=%.6f",
                    name, mae, rmse,
                )
            except Exception as exc:
                logger.warning("stacking_base_model_failed name=%s error=%s", name, exc)
                meta_features[name] = np.full(len(y_valid), np.nan)
        
        meta_df = pd.DataFrame(meta_features)
        clean_mask = meta_df.notna().all(axis=1).values
        X_meta = meta_df.values[clean_mask]
        y_clean = np.array(y_valid)[clean_mask]
        
        if len(X_meta) < 20 or np.any(np.isnan(X_meta)):
            logger.warning("stacking_meta_learner_skipped reason=insufficient_valid_data")
            self.fitted = False
            return {"status": "skipped"}
        
        self.meta_learner = Ridge(alpha=self.alpha)
        self.meta_learner.fit(X_meta, y_clean)
        self.meta_feature_names = list(meta_df.columns)
        self.fitted = True
        
        meta_pred = self.meta_learner.predict(X_meta)
        mae = mean_absolute_error(y_clean, meta_pred)
        rmse = np.sqrt(mean_squared_error(y_clean, meta_pred))
        
        weights = dict(zip(self.meta_feature_names, self.meta_learner.coef_))
        best_model = max(weights, key=lambda k: abs(weights[k]))
        
        logger.info(
            "stacking_meta_learner_trained models=%d best=%s weight=%.3f",
            len(self.base_models), best_model, weights.get(best_model, 0),
        )
        
        return {
            "status": "success",
            "meta_mae": mae,
            "meta_rmse": rmse,
            "model_weights": {k: round(v, 4) for k, v in weights.items()},
            "intercept": round(float(self.meta_learner.intercept_), 6),
            "best_model": best_model,
        }
    
    def predict(self, X: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, dict[str, Any]]:
        """Stacking集成预测
        
        Returns:
            (predictions_array, metadata_dict)
        """
        if not self.fitted or self.meta_learner is None:
            raise RuntimeError("Meta learner not fitted. Call fit_meta_learner first.")
        
        meta_input = {}
        for name, model in self.base_models.items():
            try:
                cols = [c for c in feature_cols if c in X.columns]
                meta_input[name] = model.predict(X[cols])
            except Exception:
                meta_input[name] = np.zeros(len(X))
        
        meta_df = pd.DataFrame(meta_input)[self.meta_feature_names].fillna(0.0)
        predictions = self.meta_learner.predict(meta_df.values)
        
        weights = dict(zip(self.meta_feature_names, self.meta_learner.coef_.tolist()))
        
        meta = {
            "method": "stacking_ridge",
            "base_predictions": {k: v.tolist() for k, v in meta_input.items()},
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "n_base_models": len(self.base_models),
        }
        
        return predictions, meta


def residual_adaptive_correction(
    recent_errors: list[float] | None,
    current_pred: float,
    n_window: int = 10,
) -> float:
    """残差自适应修正（Layer3）
    
    基于最近N个交易日的预测误差，修正系统偏差。
    recent_errors 为 None 或空列表时跳过修正（bias=0）。
    
    Args:
        recent_errors: 最近N次预测的历史误差序列 (predicted - actual)，
                       为None时表示无历史数据，跳过修正
        current_pred: 当前模型预测值
        n_window: 回看窗口大小
        
    Returns:
        修正后的预测值
    """
    if not recent_errors or len(recent_errors) < 3:
        return current_pred
    
    bias = np.mean(recent_errors[-n_window:])
    corrected = current_pred - bias
    
    return corrected


def build_sample_weights(n: int, halflife: int = 60) -> np.ndarray:
    """样本时间权重：指数衰减方案
    
    距今越远的样本权重越低，半衰期约halflife个交易日
    """
    weights = np.exp(-np.log(2) * np.arange(n - 1, -1, -1) / halflife)
    return weights / weights.sum()


def walk_forward_cv(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    train_months: int = 24,
    valid_months: int = 3,
    step_months: int = 21,
    min_rounds: int = 12,
    model_fn=None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Walk-Forward 时序交叉验证（增强版：动态参数适配 + 方向准确率）
    
    策略方案 §8.1 实现（V2.7 增强）：
    - 动态适配：根据实际数据量自动调整训练/验证窗口
    - Hold-out 回退：当数据量不足以支持 WF-CV 时自动降级
    - 方向准确率：每轮记录预测方向与真实方向的一致性
    
    Args:
        df: 完整时序数据
        feature_cols: 特征列
        target_col: 目标列
        train_months: 训练窗口月数（默认值，会被动态覆盖）
        valid_months: 验证窗口月数（默认值，会被动态覆盖）
        step_months: 滚动步长月数（默认值，会被动态覆盖）
        min_rounds: 最少验证轮次
        model_fn: 模型训练函数 (X_train, y_train) → model
    
    Returns:
        (results_list, aggregated_metrics)
        结果包含：actual_wf_rounds, validation_method, total_samples, direction_accuracy 等
    """
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    
    T = len(df)
    trading_days_per_month = 21
    
    dyn_train_months = max(6, int(T * 0.55 / trading_days_per_month))
    dyn_valid_months = max(2, int(T * 0.22 / trading_days_per_month))
    dyn_step_months = 1
    
    train_size = dyn_train_months * trading_days_per_month
    valid_size = dyn_valid_months * trading_days_per_month
    step_size = dyn_step_months * trading_days_per_month
    
    max_rounds_possible = (T - train_size - valid_size) / step_size if step_size > 0 else 0
    use_holdout = max_rounds_possible < 3
    
    validation_method = "holdout" if use_holdout else "walk_forward"
    
    logger.info(
        "wf_cv_dynamic_params T=%d dyn_train=%dmo dyn_valid=%dmo dyn_step=%dmo "
        "max_rounds_possible=%.1f validation_method=%s",
        T, dyn_train_months, dyn_valid_months, dyn_step_months,
        max_rounds_possible, validation_method,
    )
    
    results = []
    
    if use_holdout:
        logger.warning("wf_cv_fallback_to_holdout reason=insufficient_rounds max_rounds=%.1f", max_rounds_possible)
        
        train_end = int(T * 0.80)
        X_train_df = df.iloc[:train_end].copy()
        X_valid_df = df.iloc[train_end:].copy()
        
        if len(X_valid_df) < 10:
            logger.error("wf_cv_holdout_failed reason=insufficient_valid_data valid_n=%d", len(X_valid_df))
            return [], {
                "status": "failed",
                "validation_method": validation_method,
                "total_samples": T,
                "actual_wf_rounds": 0,
                "error": "Insufficient data for holdout validation",
            }
        
        X_train = X_train_df[feature_cols].fillna(0).values
        y_train = X_train_df[target_col].values
        X_valid = X_valid_df[feature_cols].fillna(0).values
        y_valid = X_valid_df[target_col].values
        
        sample_weights = build_sample_weights(len(y_train))
        
        try:
            if model_fn is not None:
                model = model_fn(X_train, y_train, sample_weights)
                pred = model.predict(X_valid)
            else:
                from sklearn.linear_model import Ridge
                model = Ridge(alpha=1.0)
                model.fit(X_train, y_train, sample_weight=sample_weights)
                pred = model.predict(X_valid)
            
            mae = mean_absolute_error(y_valid, pred)
            rmse = np.sqrt(mean_squared_error(y_valid, pred))
            corr = float(np.corrcoef(pred, y_valid)[0, 1]) if np.std(pred) > 0 else 0.0
            
            direction_match = np.sign(pred) == np.sign(y_valid)
            direction_accuracy = float(np.mean(direction_match))
            
            results.append({
                "round": 1,
                "train_range": (str(X_train_df.iloc[0]["date"]), str(X_train_df.iloc[-1]["date"])),
                "valid_range": (str(X_valid_df.iloc[0]["date"]), str(X_valid_df.iloc[-1]["date"])),
                "valid_n": len(X_valid_df),
                "mae": mae,
                "rmse": rmse,
                "corr": corr,
                "direction_accuracy": direction_accuracy,
            })
            
        except Exception as exc:
            logger.exception("wf_cv_holdout_failed error=%s", exc)
            return [], {
                "status": "failed",
                "validation_method": validation_method,
                "total_samples": T,
                "actual_wf_rounds": 0,
                "error": str(exc),
            }
    
    else:
        start = max(train_size, 120)
        round_num = 0
        
        for offset in range(start, T - valid_size, step_size):
            round_num += 1
            if round_num > min_rounds + 12:
                break
            
            train_end = offset
            valid_start = offset
            valid_end = min(offset + valid_size, T)
            
            train_df = df.iloc[train_end - train_size : train_end].copy()
            valid_df = df.iloc[valid_start:valid_end].copy()
            
            if len(valid_df) < 20:
                continue
            
            X_train = train_df[feature_cols].fillna(0).values
            y_train = train_df[target_col].values
            X_valid = valid_df[feature_cols].fillna(0).values
            y_valid = valid_df[target_col].values
            
            sample_weights = build_sample_weights(len(y_train))
            
            if model_fn is not None:
                try:
                    model = model_fn(X_train, y_train, sample_weights)
                    pred = model.predict(X_valid)
                except Exception as exc:
                    logger.warning("wf_cv_round_failed round=%d error=%s", round_num, exc)
                    continue
            else:
                from sklearn.linear_model import Ridge
                model = Ridge(alpha=1.0)
                model.fit(X_train, y_train, sample_weight=sample_weights)
                pred = model.predict(X_valid)
            
            mae = mean_absolute_error(y_valid, pred)
            rmse = np.sqrt(mean_squared_error(y_valid, pred))
            corr = float(np.corrcoef(pred, y_valid)[0, 1]) if np.std(pred) > 0 else 0.0
            
            direction_match = np.sign(pred) == np.sign(y_valid)
            direction_accuracy = float(np.mean(direction_match))
            
            results.append({
                "round": round_num,
                "train_range": (str(train_df.iloc[0]["date"]), str(train_df.iloc[-1]["date"])),
                "valid_range": (str(valid_df.iloc[0]["date"]), str(valid_df.iloc[-1]["date"])),
                "valid_n": len(valid_df),
                "mae": mae,
                "rmse": rmse,
                "corr": corr,
                "direction_accuracy": direction_accuracy,
            })
    
    logger.info("walk_forward_cv_completed rounds=%d method=%s", len(results), validation_method)
    
    if results:
        agg = {
            "mean_mae": round(np.mean([r["mae"] for r in results]), 6),
            "median_mae": round(float(np.median([r["mae"] for r in results])), 6),
            "mean_rmse": round(np.mean([r["rmse"] for r in results]), 6),
            "mean_corr": round(np.mean([r["corr"] for r in results]), 4),
            "mean_direction_accuracy": round(np.mean([r.get("direction_accuracy", 0.5) for r in results]), 4),
            "worst_mae": round(max(r["mae"] for r in results), 6),
            "best_mae": round(min(r["mae"] for r in results), 6),
            "total_rounds": len(results),
            "validation_method": validation_method,
            "total_samples": T,
            "actual_wf_rounds": len(results),
        }
        return results, agg
    
    return results, {
        "status": "no_valid_rounds",
        "validation_method": validation_method,
        "total_samples": T,
        "actual_wf_rounds": 0,
    }
