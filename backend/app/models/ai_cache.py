from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class AiAnalysisCache(Base):
    __tablename__ = "ai_analysis_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String, nullable=False)
    trade_date = Column(String, nullable=False)
    analysis_json = Column(Text, nullable=False)
    provider_used = Column(String, nullable=True)
    model_used = Column(String, nullable=True)
    news_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, default=func.now())

    __table_args__ = (
        UniqueConstraint("fund_code", "trade_date", name="uq_ai_cache_code_date"),
    )