from sqlalchemy import Column, String, Integer, Float, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.core.database import Base


class FundProfileCache(Base):
    __tablename__ = "fund_profile_cache"

    fund_code = Column(String, primary_key=True)
    fund_name = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    fund_type_raw = Column(String, nullable=True)
    fund_type = Column(String, nullable=True)
    manager = Column(String, nullable=True)
    company = Column(String, nullable=True)
    size_text = Column(String, nullable=True)
    benchmark = Column(String, nullable=True)
    invest_strategy = Column(Text, nullable=True)
    rating = Column(String, nullable=True)
    established = Column(String, nullable=True)
    skip_prediction = Column(Integer, default=0)
    classification_confidence = Column(Float, nullable=True)
    profile_json = Column(Text, nullable=True)
    cached_at = Column(TIMESTAMP, default=func.now())