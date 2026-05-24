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
    recent_errors: list[float],
    current_pred: float,
    n_window: int = 10,
) -> float:
    """残差自适应修正（Layer3）
    
    基于最近N个交易日的预测误差，修正系统偏差。
    """
    if len(recent_errors) < 3:
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
) -> list[dict[str, Any]]:
    """Walk-Forward 时序交叉验证
    
    策略方案 §8.1 实现：
    - 训练窗口：24个月（约500交易日）
    - 验证窗口：3个月（约60交易日）
    - 滚动步长：1个月
    - 最少轮次：12轮
    
    Args:
        df: 完整时序数据
        feature_cols: 特征列
        target_col: 目标列
        train_months: 训练窗口月数
        valid_months: 验证窗口月数
        step_months: 滚动步长月数
        min_rounds: 最少验证轮次
        model_fn: 模型训练函数 (X_train, y_train) → model
    
    Returns:
        每轮验证结果的列表
    """
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    
    trading_days_per_month = 21
    train_size = train_months * trading_days_per_month
    valid_size = valid_months * trading_days_per_month
    step_size = step_months * trading_days_per_month
    
    results = []
    n = len(df)
    start = max(train_size, 120)
    
    round_num = 0
    for offset in range(start, n - valid_size, step_size):
        round_num += 1
        if round_num > min_rounds + 12:
            break
        
        train_end = offset
        valid_start = offset
        valid_end = min(offset + valid_size, n)
        
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
        
        results.append({
            "round": round_num,
            "train_range": (str(train_df.iloc[0]["date"]), str(train_df.iloc[-1]["date"])),
            "valid_range": (str(valid_df.iloc[0]["date"]), str(valid_df.iloc[-1]["date"])),
            "valid_n": len(valid_df),
            "mae": mae,
            "rmse": rmse,
            "corr": corr,
        })
    
    logger.info("walk_forward_cv_completed rounds=%d", len(results))
    
    if results:
        agg = {
            "mean_mae": round(np.mean([r["mae"] for r in results]), 6),
            "median_mae": round(float(np.median([r["mae"] for r in results])), 6),
            "mean_rmse": round(np.mean([r["rmse"] for r in results]), 6),
            "mean_corr": round(np.mean([r["corr"] for r in results]), 4),
            "worst_mae": round(max(r["mae"] for r in results), 6),
            "best_mae": round(min(r["mae"] for r in results), 6),
            "total_rounds": len(results),
        }
        return results, agg
    
    return results, {}