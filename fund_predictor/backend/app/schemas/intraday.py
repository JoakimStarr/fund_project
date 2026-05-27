from typing import Optional
from pydantic import BaseModel
from app.schemas.predict import ConfidenceInterval

class IntradayRequest(BaseModel):
    mode: str = "auto"

class HoldingContribution(BaseModel):
    rank: int
    code: str
    name: str
    weight: float
    price: float = 0
    prev_close: float = 0
    pct_change: float = 0
    contribution: float = 0

class IntradayResponse(BaseModel):
    fund_code: str
    fund_name: str = ""
    estimated_nav: float = 0
    prev_nav: float = 0
    estimated_return: float = 0
    estimated_return_pct: float = 0
    confidence_interval: Optional[ConfidenceInterval] = None
    confidence: str = "medium"
    method: str = ""
    method_display: str = ""
    market_session: dict = {}
    holdings_used: list = []
    holdings_freshness: Optional[dict] = None
    index_comparison: Optional[dict] = None
    timestamp: str = ""