from typing import Optional
from pydantic import BaseModel

class TrainRequest(BaseModel):
    fund_code: str
    force_retrain: bool = False

class TrainTaskResponse(BaseModel):
    task_id: str
    fund_code: str
    status: str
    message: str = ""