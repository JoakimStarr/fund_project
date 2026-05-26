import numpy as np


def calibrate(model, X_calib: np.ndarray, y_calib: np.ndarray, alpha: float = 0.10) -> dict:
    preds = model.predict(X_calib)
    residuals = np.abs(preds - y_calib)
    n = len(residuals)
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    q_value = float(np.quantile(residuals, q_level))
    return {
        "calibration_size": n,
        "q_level": float(q_level),
        "q_value": q_value,
        "alpha": alpha,
        "residuals": residuals.tolist(),
        "residual_mean": float(np.mean(residuals)),
        "residual_std": float(np.std(residuals)),
    }


def predict_interval(model, X: np.ndarray, calib_residuals: dict, alpha: float = 0.10) -> tuple:
    preds = model.predict(X)
    q_value = calib_residuals.get("q_value", 0.0)
    lower = preds - q_value
    upper = preds + q_value
    return preds, lower, upper