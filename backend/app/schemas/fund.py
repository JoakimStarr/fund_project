from typing import Optional
from pydantic import BaseModel


class FundValidateRequest(BaseModel):
    raw_input: str


class FundValidateResponse(BaseModel):
    raw_input: str
    normalized: str
    is_valid: bool
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    skip_prediction: Optional[bool] = None
    normalization_steps: Optional[list] = None


class FundRollbackRequest(BaseModel):
    version: str


class FundSearchResult(BaseModel):
    fund_code: str
    fund_name: str
    fund_type_raw: Optional[str] = None
    fund_type: Optional[str] = None
    company: Optional[str] = None
    size_text: Optional[str] = None