from typing import Optional
from pydantic import BaseModel

class AiAnalysisRequest(BaseModel):
    fund_code: str
    context: dict = {}
    refresh: bool = False

class AiAnalysisResponse(BaseModel):
    fund_code: str
    trade_date: str
    analysis: dict
    news_used: list = []
    provider_used: str = ""
    model_used: str = ""
    tokens_used: int = 0
    cached: bool = False
    generated_at: str = ""