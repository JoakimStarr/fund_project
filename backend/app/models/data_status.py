from sqlalchemy import Column, Integer, String, TIMESTAMP, UniqueConstraint
from app.core.database import Base


class DataStatus(Base):
    __tablename__ = "data_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String, nullable=False)
    identifier = Column(String, nullable=False)
    latest_date = Column(String, nullable=True)
    row_count = Column(Integer, default=0)
    last_updated = Column(TIMESTAMP, nullable=True)
    status = Column(String, default="ok")

    __table_args__ = (
        UniqueConstraint("data_type", "identifier", name="uq_data_status_type_id"),
    )