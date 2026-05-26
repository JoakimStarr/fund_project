import numpy as np
from sklearn.linear_model import Ridge
from lightgbm import LGBMRegressor


class StackingModel:
    def __init__(self):
        self.base_ridge = Ridge(alpha=1.0)
        self.base_lgbm = LGBMRegressor(n_estimators=120, max_depth=5, learning_rate=0.05, min_child_samples=10, verbose=-1)
        self.meta_model = Ridge(alpha=1.0)
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.base_ridge.fit(X, y)
        self.base_lgbm.fit(X, y)
        p1 = self.base_ridge.predict(X).reshape(-1, 1)
        p2 = self.base_lgbm.predict(X).reshape(-1, 1)
        meta_X = np.hstack([p1, p2])
        self.meta_model.fit(meta_X, y)
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        p1 = self.base_ridge.predict(X).reshape(-1, 1)
        p2 = self.base_lgbm.predict(X).reshape(-1, 1)
        meta_X = np.hstack([p1, p2])
        return self.meta_model.predict(meta_X)

    def get_feature_importance(self) -> dict:
        result = {}
        ridge_coefs = self.base_ridge.coef_
        if ridge_coefs is not None:
            result["ridge_coefficient_mean"] = float(np.mean(np.abs(ridge_coefs)))
        meta_coefs = self.meta_model.coef_
        if meta_coefs is not None and len(meta_coefs) > 1:
            result["ridge_weight"] = float(meta_coefs[0])
            result["lgbm_weight"] = float(meta_coefs[1])
        try:
            lgbm_importances = self.base_lgbm.feature_importances_
            if lgbm_importances is not None:
                result["lgbm_importance_mean"] = float(np.mean(lgbm_importances))
        except Exception:
            pass
        return result