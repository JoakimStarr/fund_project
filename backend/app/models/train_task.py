from sqlalchemy import Column, String, Integer, TIMESTAMP, Text, Index, desc
from sqlalchemy.sql import func
from app.core.database import Base


class TrainTask(Base):
    __tablename__ = "train_task"

    id = Column(String, primary_key=True)
    fund_code = Column(String, nullable=False)
    status = Column(String, default="pending")
    force_retrain = Column(Integer, default=0)
    progress = Column(Integer, default=0)
    log_text = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    model_version = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, default=func.now())
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("idx_train_task_code_date", "fund_code", desc("created_at")),
    )