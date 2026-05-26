from typing import Optional
from pydantic import BaseModel

from backend.app.schemas.predict import ConfidenceInterval


class IntradayRequest(BaseModel):
    mode: str = "auto"


class HoldingContribution(BaseModel):
    rank: int
    code: str
    name: str
    weight: float
    price: Optional[float] = None
    prev_close: Optional[float] = None
    pct_change: float
    contribution: float


class MarketSession(BaseModel):
    is_trading: bool
    session: str
    note: str


class IntradayResponse(BaseModel):
    fund_code: str
    fund_name: Optional[str] = None
    estimated_nav: float
    prev_nav: Optional[float] = None
    estimated_return: float
    estimated_return_pct: float
    confidence_interval: Optional[ConfidenceInterval] = None
    confidence: str
    method: str
    method_display: str
    market_session: MarketSession
    holdings_used: Optional[list[HoldingContribution]] = None
    holdings_freshness: Optional[dict] = None
    timestamp: str