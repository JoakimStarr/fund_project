from typing import Optional
from pydantic import BaseModel

class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence_level: float = 0.90

class ModelInfo(BaseModel):
    model_type: str
    base_models: list = []
    mae: float = 0
    direction_accuracy: float = 0
    features_used: int = 0
    trained_date: str = ""
    model_version: str = ""
    wfcv_rounds: int = 0

class ConstraintInfo(BaseModel):
    is_clipped: bool = False
    original_return: float = 0
    limit: float = 0

class FundHealth(BaseModel):
    data_sufficiency: str = ""
    data_days: int = 0
    data_freshness: str = ""
    latest_nav_date: str = ""
    model_age_days: int = 0
    prediction_reliability: str = ""
    warnings: list = []

class ShapFactor(BaseModel):
    factor: str
    contribution: float
    direction: str
    display: str = ""

class PredictResponse(BaseModel):
    fund_code: str
    fund_name: str = ""
    fund_type: str = ""
    predict_date: str
    target_date: str
    predicted_return: float
    predicted_nav: float = 0
    prev_nav: float = 0
    confidence_interval: ConfidenceInterval
    direction: str
    direction_probability: float
    confidence: str = "medium"
    model_info: Optional[ModelInfo] = None
    constraint_info: Optional[ConstraintInfo] = None
    fund_health: Optional[FundHealth] = None
    shap_top_factors: list = []