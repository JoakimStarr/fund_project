from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    fund_code: str = Field(min_length=3, max_length=12)
    force_retrain: bool = False


class TrainRequest(BaseModel):
    fund_code: str = Field(min_length=3, max_length=12)
    force: bool = True
