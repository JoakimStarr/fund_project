from typing import Optional
from pydantic import BaseModel

class FundPredictRequest(BaseModel):
    fund_code: str
    force_retrain: bool = False

class FundValidateRequest(BaseModel):
    raw_input: str

class FundValidateResponse(BaseModel):
    raw_input: str
    normalized: str
    is_valid: bool
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    skip_prediction: bool = False
    normalization_steps: list = []
    error_message: Optional[str] = None

class FundBatchPredictRequest(BaseModel):
    fund_codes: list[str]

class FundRollbackRequest(BaseModel):
    version: str

class FundSearchResult(BaseModel):
    fund_code: str
    fund_name: str
    fund_type_raw: Optional[str] = None
    fund_type: Optional[str] = None
    company: Optional[str] = None
    size_text: Optional[str] = None

PredictRequest = FundPredictRequest
from app.schemas.train import TrainRequest