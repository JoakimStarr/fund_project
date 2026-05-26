from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.core.database import Base


class NewsCache(Base):
    __tablename__ = "news_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String, nullable=False, unique=True)
    news_json = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())