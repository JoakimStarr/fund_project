from typing import Any


class AppError(Exception):
    code = "APP_ERROR"
    stage = "unknown"

    def __init__(self, message: str, stage: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        if stage:
            self.stage = stage
        self.details = details or {}

    def to_dict(self, request_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "request_id": request_id,
            "task_id": task_id,
            "details": self.details,
        }


class DataFetchError(AppError):
    code = "DATA_FETCH_FAILED"
    stage = "data_fetch"


class DataStaleError(AppError):
    code = "DATA_STALE"
    stage = "data_fetch"


class InsufficientDataError(AppError):
    code = "INSUFFICIENT_DATA"
    stage = "data_validation"


class FeatureBuildError(AppError):
    code = "FEATURE_BUILD_FAILED"
    stage = "feature_build"


class ModelSelectionError(AppError):
    code = "MODEL_SELECTION_FAILED"
    stage = "model_selection"


class ModelNotFoundError(AppError):
    code = "MODEL_NOT_FOUND"
    stage = "model_registry"


class PredictionError(AppError):
    code = "PREDICTION_FAILED"
    stage = "prediction"


class PredictionFeatureMissingError(PredictionError):
    code = "PREDICTION_FEATURE_MISSING"
    stage = "prediction"


class DirectionModelError(AppError):
    code = "DIRECTION_MODEL_FAILED"
    stage = "direction_model"


class ProbabilityCalibrationError(AppError):
    code = "PROBABILITY_CALIBRATION_FAILED"
    stage = "direction_model_calibration"


class BaselineEvalError(AppError):
    code = "BASELINE_EVAL_FAILED"
    stage = "baseline_eval"


class RegimeIntervalError(AppError):
    code = "REGIME_INTERVAL_FAILED"
    stage = "regime_interval"


class HoldingFetchError(AppError):
    code = "HOLDING_FETCH_FAILED"
    stage = "holding_fetch"


class StockPriceFetchError(AppError):
    code = "STOCK_PRICE_FETCH_FAILED"
    stage = "stock_price_fetch"


class ThemeProxyError(AppError):
    code = "THEME_PROXY_FAILED"
    stage = "theme_proxy"


class ProxyPortfolioError(AppError):
    code = "PROXY_PORTFOLIO_FAILED"
    stage = "proxy_portfolio"


class ProxyExposureError(AppError):
    code = "PROXY_EXPOSURE_FAILED"
    stage = "proxy_exposure"


class DuplicateFeatureColumnsError(AppError):
    code = "DUPLICATE_FEATURE_COLUMNS"
    stage = "feature_engineering"


class ModelTrainingFailedError(AppError):
    code = "MODEL_TRAINING_FAILED"
    stage = "training"
