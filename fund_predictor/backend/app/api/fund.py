import logging

import pandas as pd
from fastapi import APIRouter

from backend.app.core.errors import AppError, ModelNotFoundError, ModelTrainingFailedError
from backend.app.core.logging_config import request_id_var, set_log_context
from backend.app.schemas.fund import PredictRequest
from backend.app.services.model_registry_service import get_model_info, model_exists
from backend.app.services.prediction_service import predict_next
from backend.app.services.task_service import get_latest_task

router = APIRouter(prefix="/api/fund", tags=["fund"])
logger = logging.getLogger(__name__)


@router.post("/predict")
def predict(req: PredictRequest):
    fund_code = req.fund_code.strip()
    set_log_context(fund_code=fund_code)
    if not model_exists(fund_code):
        latest_task = get_latest_task(fund_code)
        if latest_task and latest_task.get("status") == "failed":
            raise ModelTrainingFailedError(
                "上一次训练失败，模型未保存，请查看日志。",
                details={
                    "fund_code": fund_code,
                    "task_id": latest_task.get("task_id"),
                    "error_code": latest_task.get("error_code"),
                    "error_stage": latest_task.get("stage"),
                    "error_message": latest_task.get("error_message"),
                },
            )
        raise ModelNotFoundError("该基金尚未训练，请点击训练并预测", details={"fund_code": fund_code})
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
