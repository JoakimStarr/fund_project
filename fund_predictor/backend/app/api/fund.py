import logging

import pandas as pd
from fastapi import APIRouter

from app.core.errors import AppError, ModelNotFoundError, ModelTrainingFailedError
from app.core.logging_config import request_id_var, set_log_context
from app.schemas.fund import PredictRequest
from app.services.fund_profile_service import classify_fund
from app.services.model_registry_service import get_model_info, model_exists
from app.services.prediction_service import predict_next
from app.services.routing_service import route_predict
from app.services.task_service import get_latest_task

router = APIRouter(prefix="/api/fund", tags=["fund"])
logger = logging.getLogger(__name__)


@router.post("/predict")
def predict(req: PredictRequest):
    fund_code = req.fund_code.strip()
    set_log_context(fund_code=fund_code)
    
    # 获取基金画像
    profile = classify_fund(fund_code)
    
    # 货币基金直接返回
    if profile.skip_prediction:
        return {
            "ok": True,
            "data": {
                "fund_code": fund_code,
                "fund_type": profile.fund_type,
                "message": "货币基金净值恒为1，无需预测",
                "fund_profile": {
                    "type": profile.fund_type,
                    "name": profile.fund_name,
                },
            },
        }
    
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
    
    # 路由分发
    data = route_predict(fund_code, profile, request_id_var.get())
    return {"ok": True, "data": data}


@router.get("/{fund_code}/profile")
def fund_profile(fund_code: str):
    """获取基金画像信息"""
    set_log_context(fund_code=fund_code)
    profile = classify_fund(fund_code)
    return {
        "ok": True,
        "data": {
            "fund_code": profile.fund_code,
            "fund_type": profile.fund_type,
            "fund_name": profile.fund_name,
            "fund_size": profile.fund_size,
            "manager": profile.manager,
            "benchmark": profile.benchmark,
            "strategy_keywords": profile.strategy_keywords,
            "skip_prediction": profile.skip_prediction,
        },
    }


@router.get("/{fund_code}/model")
def model_info(fund_code: str):
    set_log_context(fund_code=fund_code)
    return {"ok": True, "data": get_model_info(fund_code)}


@router.get("/{fund_code}/backtest")
def backtest(fund_code: str):
    from app.services.model_registry_service import fund_model_dir

    path = fund_model_dir(fund_code) / "backtest.csv"
    if not path.exists():
        raise ModelNotFoundError("回测文件不存在", details={"fund_code": fund_code})
    df = pd.read_csv(path)
    return {"ok": True, "data": df.to_dict(orient="records")}
