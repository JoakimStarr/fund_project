from typing import Optional
from pydantic import BaseModel


class AiAnalysisRequest(BaseModel):
    fund_code: str
    context: Optional[dict] = None
    refresh: bool = False


class AiAnalysisResponse(BaseModel):
    fund_code: str
    trade_date: str
    analysis: dict
    news_used: Optional[list] = None
    holdings_freshness: Optional[dict] = None
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    cached: bool
    generated_at: Optional[str] = None