import numpy as np
from app.schemas.predict import ShapFactor


def explain(model, X: np.ndarray, feature_names: list, top_n: int = 5) -> list:
    try:
        import shap
        explainer = shap.Explainer(model, X)
        shap_values = explainer(X)
        if hasattr(shap_values, "values"):
            values = shap_values.values
        else:
            values = shap_values
        if isinstance(values, np.ndarray) and values.ndim > 1:
            if values.ndim == 3:
                values = values[:, :, 0] if values.shape[2] > 0 else values[:, :, 0]
            values = values[0] if values.shape[0] > 0 else values
        if isinstance(values, np.ndarray):
            values = values.flatten()
        indices = np.argsort(np.abs(values))[::-1][:top_n]
        factors = []
        for i in indices:
            name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
            contrib = float(values[i])
            direction = "正向" if contrib > 0 else "负向"
            display = f"{name}: {contrib:+.6f}"
            factors.append(ShapFactor(factor=name, contribution=contrib, direction=direction, display=display))
        return factors
    except Exception:
        return _fallback_coefficients(model, feature_names, top_n)


def _fallback_coefficients(model, feature_names: list, top_n: int = 5) -> list:
    try:
        if hasattr(model, "coef_") and model.coef_ is not None:
            coefs = model.coef_
            if hasattr(coefs, "flatten"):
                coefs = coefs.flatten()
            indices = np.argsort(np.abs(coefs))[::-1][:top_n]
            factors = []
            for i in indices:
                name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
                contrib = float(coefs[i])
                direction = "正向" if contrib > 0 else "负向"
                display = f"{name}: {contrib:+.6f}"
                factors.append(ShapFactor(factor=name, contribution=contrib, direction=direction, display=display))
            return factors
    except Exception:
        pass
    return []