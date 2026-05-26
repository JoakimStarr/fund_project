import numpy as np
from sklearn.metrics import mean_absolute_error
from app.core.errors import InsufficientDataError


def calc_wfcv_params(n_rows: int) -> dict:
    if n_rows < 150:
        raise InsufficientDataError(f"数据行数 {n_rows} 不足 150 行")
    if n_rows >= 500:
        train_window = 500
        max_rounds = 24
    elif n_rows >= 300:
        train_window = 250
        max_rounds = 12
    else:
        train_window = int(n_rows * 0.55)
        max_rounds = 6
    valid_window = max(40, int(train_window * 0.2))
    step_size = valid_window
    available = (n_rows - train_window - valid_window) // step_size
    actual_rounds = max(3, min(available, max_rounds))
    degraded = actual_rounds < 6
    return {
        "train_window": train_window,
        "valid_window": valid_window,
        "step_size": step_size,
        "actual_rounds": actual_rounds,
        "degraded": degraded,
    }


def run_wfcv(model_class, model_params: dict, X: np.ndarray, y: np.ndarray, params: dict) -> list:
    n = len(X)
    rounds = []
    for i in range(params["actual_rounds"]):
        train_end = n - (params["actual_rounds"] - i) * params["step_size"]
        valid_end = train_end + params["valid_window"]
        if valid_end > n:
            break
        train_start = max(0, train_end - params["train_window"])
        X_train, y_train = X[train_start:train_end], y[train_start:train_end]
        X_valid, y_valid = X[train_end:valid_end], y[train_end:valid_end]
        model = model_class(**model_params)
        model.fit(X_train, y_train)
        pred = model.predict(X_valid)
        mae = float(mean_absolute_error(y_valid, pred))
        direction_acc = float(np.mean((pred > 0) == (y_valid > 0)))
        rounds.append({"round": i + 1, "mae": mae, "direction_accuracy": direction_acc, "train_size": len(X_train), "valid_size": len(X_valid)})
    if len(rounds) < 3:
        return rounds
    return rounds