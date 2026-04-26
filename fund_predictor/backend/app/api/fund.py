import logging

import pandas as pd
from fastapi import APIRouter

from backend.app.core.errors import AppError, ModelNotFoundError
from backend.app.core.logging_config import request_id_var, set_log_context
from backend.app.schemas.fund import PredictRequest
from backend.app.services.model_registry_service import get_model_info, should_retrain
from backend.app.services.prediction_service import predict_next

router = APIRouter(prefix="/api/fund", tags=["fund"])
logger = logging.getLogger(__name__)


@router.post("/predict")
def predict(req: PredictRequest):
    fund_code = req.fund_code.strip()
    set_log_context(fund_code=fund_code)
    if should_retrain(fund_code, force_retrain=req.force_retrain):
        raise ModelNotFoundError("该基金尚未训练或需要重训，请点击训练并预测", details={"fund_code": fund_code})
    data = predict_next(fund_code, request_id_var.get())
    return {"ok": True, "data": data}


@router.get("/{fund_code}/model")
def model_info(fund_code: str):
    set_log_context(fund_code=fund_code)
    return {"ok": True, "data": get_model_info(fund_code)}


@router.get("/{fund_code}/backtest")
def backtest(fund_code: str):
    from backend.app.services.model_registry_service import fund_model_dir

    path = fund_model_dir(fund_code) / "backtest.csv"
    if not path.exists():
        raise ModelNotFoundError("回测文件不存在", details={"fund_code": fund_code})
    df = pd.read_csv(path)
    return {"ok": True, "data": df.to_dict(orient="records")}
