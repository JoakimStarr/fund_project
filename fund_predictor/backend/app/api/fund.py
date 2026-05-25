import logging
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter

from app.core.errors import AppError, ModelNotFoundError, ModelTrainingFailedError
from app.core.logging_config import request_id_var, set_log_context
from app.db.database import get_conn
from app.schemas.fund import PredictRequest
from app.services.fund_profile_service import get_profile, invalidate_profile_cache
from app.services.model_registry_service import get_model_info, model_exists
from app.services.prediction_service import predict_next
from app.services.routing_service import route_predict
from app.services.task_service import get_latest_task

router = APIRouter(prefix="/api/v1/fund", tags=["fund"])
logger = logging.getLogger(__name__)


@router.post("/predict")
def predict(req: PredictRequest):
    fund_code = req.fund_code.strip()
    set_log_context(fund_code=fund_code)
    
    profile = get_profile(fund_code)
    
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
    
    data = route_predict(fund_code, profile, request_id_var.get())
    return {"ok": True, "data": data}


@router.get("/{fund_code}/profile")
def fund_profile(fund_code: str, force_refresh: bool = False):
    """获取基金画像信息（带DB缓存）"""
    set_log_context(fund_code=fund_code)
    profile = get_profile(fund_code, force_refresh=force_refresh)

    now = datetime.now(timezone.utc).isoformat()
    fetched_at = profile.cached_at or now
    ttl_days = 7

    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        expires_at = (dt.replace(tzinfo=timezone.utc).__class__(dt.year, dt.month, dt.day + ttl_days)).isoformat()
    except Exception:
        expires_at = ""

    return {
        "ok": True,
        "data": {
            "fund_code": profile.fund_code,
            "fund_name": profile.fund_name,
            "fund_type": profile.fund_type,
            "fund_type_raw": profile.fund_type_raw,
            "establish_date": profile.establish_date,
            "fund_size": profile.fund_size,
            "manager": profile.manager,
            "fee_rate": profile.fee_rate,
            "benchmark": profile.benchmark,
            "strategy_text": profile.strategy_text,
            "strategy_keywords": profile.strategy_keywords,
            "skip_prediction": profile.skip_prediction,
            "risk_level": profile.risk_level,
            "cache_info": {
                "cached": bool(profile.cached_at) and not profile.stale,
                "fetched_at": profile.cached_at or "",
                "expires_at": expires_at,
                "ttl_days": ttl_days,
                "data_source": "akshare",
                "stale": profile.stale,
            },
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
    df = df.where(pd.notnull(df), None)
    return {"ok": True, "data": df.to_dict(orient="records")}


admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@admin_router.get("/data-status")
def data_status():
    with get_conn() as conn:
        tables = ["tasks", "fund_profiles", "fund_nav", "index_data", "holdings", "train_results", "data_fetch_log"]
        result = {}
        for t in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                result[t] = {"rows": count}
                if t == "fund_nav":
                    row = conn.execute("SELECT MAX(trade_date) FROM fund_nav").fetchone()
                    if row and row[0]:
                        result[t]["latest_date"] = row[0]
                if t == "fund_profiles":
                    row = conn.execute("SELECT COUNT(CASE WHEN fetched_at > datetime('now','-7 days') THEN 1 END) FROM fund_profiles").fetchone()
                    result[t]["fresh_count"] = row[0] or 0
            except Exception:
                result[t] = {"rows": 0, "error": "table_not_ready"}
    return {"ok": True, "data": result}


@admin_router.delete("/cache/{fund_code}")
def clear_cache(fund_code: str):
    ok = invalidate_profile_cache(fund_code)
    return {"ok": ok, "data": {"fund_code": fund_code, "cache_cleared": ok}}
