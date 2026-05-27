from typing import Optional
from pydantic import BaseModel


class PathResult(BaseModel):
    return_val: float
    return_pct: float
    available: bool
    meta: Optional[dict] = None


class FusionWeight(BaseModel):
    path_a: float
    path_b: float


class MarketSession(BaseModel):
    is_trading: bool
    session: str
    note: str


class HoldingContribution(BaseModel):
    rank: int
    code: str
    name: str
    weight: float
    pct_change: float
    contribution: float
    price: Optional[float] = None
    prev_close: Optional[float] = None


class PredictResponse(BaseModel):
    fund_code: str
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    prev_nav: float
    prev_date: str
    predicted_return: float
    predicted_nav: float
    confidence_interval_lower: float = 0.0
    confidence_interval_upper: float = 0.0
    direction: str
    direction_probability: float
    confidence: float
    model_info: Optional[dict] = None
    method: str = "dual_path_fusion"
    method_display: str = "双路径融合法"
    path_a: PathResult
    path_b: PathResult
    fusion_weight: FusionWeight
    holdings_used: Optional[list] = None
    market_session: MarketSession
    timestamp: str
