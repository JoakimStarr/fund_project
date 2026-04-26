from typing import Any

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    fund_code: str
    asof_date: str
    pred: float
    lower_90: float
    upper_90: float
    best_model: str
    selector: str
    scaler: str
    metrics: dict[str, Any]
    selected_feature_count: int
    stale: bool
    request_id: str
