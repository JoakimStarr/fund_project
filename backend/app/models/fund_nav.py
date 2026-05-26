from sqlalchemy import Column, Integer, String, Float, TIMESTAMP, UniqueConstraint, Index, desc
from sqlalchemy.sql import func
from app.core.database import Base


class FundNav(Base):
    __tablename__ = "fund_nav"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String, nullable=False, index=True)
    nav_date = Column(String, nullable=False)
    nav = Column(Float, nullable=False)
    acc_nav = Column(Float, nullable=True)
    daily_return = Column(Float, nullable=True)
    adj_nav = Column(Float, nullable=True)
    source = Column(String, default="em")
    created_at = Column(TIMESTAMP, default=func.now())

    __table_args__ = (
        UniqueConstraint("fund_code", "nav_date", name="uq_fund_nav_code_date"),
        Index("idx_fund_nav_code_date", "fund_code", desc("nav_date")),
    )