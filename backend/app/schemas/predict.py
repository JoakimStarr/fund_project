from typing import Optional
from pydantic import BaseModel


class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence_level: float = 0.90


class ModelInfo(BaseModel):
    model_type: str
    base_models: Optional[list] = None
    mae: Optional[float] = None
    direction_accuracy: Optional[float] = None
    features_used: Optional[int] = None
    trained_date: Optional[str] = None
    model_version: Optional[str] = None
    wfcv_rounds: Optional[int] = None


class ConstraintInfo(BaseModel):
    is_clipped: bool
    original_return: Optional[float] = None
    limit: Optional[float] = None


class FundHealth(BaseModel):
    data_sufficiency: str
    data_days: int
    data_freshness: str
    latest_nav_date: str
    model_age_days: Optional[int] = None
    prediction_reliability: str
    warnings: Optional[list] = None


class ShapFactor(BaseModel):
    factor: str
    contribution: float
    direction: str
    display: str


class PredictResponse(BaseModel):
    fund_code: str
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    predict_date: str
    target_date: str
    predicted_return: float
    predicted_nav: Optional[float] = None
    prev_nav: Optional[float] = None
    confidence_interval: ConfidenceInterval
    direction: str
    direction_probability: float
    confidence: str
    model_info: Optional[ModelInfo] = None
    constraint_info: Optional[ConstraintInfo] = None
    special_period_adjustments: Optional[list] = None
    fund_health: Optional[FundHealth] = None
    shap_top_factors: Optional[list[ShapFactor]] = None