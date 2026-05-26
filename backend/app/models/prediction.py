from sqlalchemy import Column, Integer, String, Float, TIMESTAMP, UniqueConstraint, Index, desc
from sqlalchemy.sql import func
from app.core.database import Base


class Prediction(Base):
    __tablename__ = "prediction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String, nullable=False)
    predict_date = Column(String, nullable=False)
    target_date = Column(String, nullable=False)
    predicted_return = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=False)
    upper_bound = Column(Float, nullable=False)
    direction = Column(String, nullable=False)
    direction_prob = Column(Float, nullable=False)
    confidence_level = Column(Float, default=0.90)
    model_type = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    features_used = Column(Integer, nullable=True)
    fund_type = Column(String, nullable=True)
    actual_return = Column(Float, nullable=True)
    error = Column(Float, nullable=True)
    direction_correct = Column(Integer, nullable=True)
    interval_covered = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, default=func.now())

    __table_args__ = (
        UniqueConstraint("fund_code", "predict_date", "target_date", name="uq_prediction_code_date_target"),
        Index("idx_prediction_code_date", "fund_code", desc("predict_date")),
    )