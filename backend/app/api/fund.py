import asyncio
from fastapi import APIRouter, Query, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.fund import FundPredictRequest, FundValidateRequest, FundValidateResponse, FundBatchPredictRequest, FundRollbackRequest, FundSearchResult
from app.services.fund.normalizer import normalize as normalize_fund_code
from app.services.fund.profile_service import get_profile as fetch_profile
from app.services.predict.prediction_service import predict as do_predict
from app.services.model.versioning import rollback as rollback_model
from app.services.data.danjuan_client import search_funds as dj_search, get_fund_info as dj_get_info

router = APIRouter(prefix="/fund", tags=["fund"])


@router.post("/predict")
async def predict(req: FundPredictRequest, db=Depends(get_db)):
    try:
        result = await do_predict(req.fund_code, db)
        return ApiResponse(ok=True, data=result.model_dump())
    except ValueError as e:
        return ApiResponse(ok=False, error={"code": "PREDICT_ERROR", "message": str(e), "status": 422})
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "PREDICT_ERROR", "message": str(e), "status": 500})


@router.get("/search")
async def search_funds(q: str = Query(...)):
    try:
        results = await dj_search(q)
        return ApiResponse(ok=True, data=results)
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "SEARCH_ERROR", "message": str(e), "status": 500})


@router.post("/validate")
async def validate_fund(req: FundValidateRequest):
    from app.services.data.danjuan_client import get_fund_info as dj_get_info
    from app.services.fund.routing_service import classify
    
    raw = req.raw_input.strip()
    
    import re
    text = raw.replace("\u3000", " ")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"\.(OF|SH|SZ)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(sh|sz)", "", text, flags=re.IGNORECASE)
    
    is_valid_format = bool(re.match(r"^\d{6}$", text))
    if not is_valid_format and re.match(r"^\d+$", text):
        while len(text) < 6:
            text = "0" + text
        is_valid_format = True
    
    fund_name = ""
    fund_type = None
    skip_prediction = None
    
    if is_valid_format:
        try:
            info = await dj_get_info(text)
            fund_name = info.get("fund_name", "")
            if fund_name:
                classification = classify(fund_name, "", "", "")
                fund_type = classification["fund_type"]
                if fund_type == "money_market":
                    skip_prediction = True
        except Exception as e:
            pass
    
    return ApiResponse(ok=True, data=FundValidateResponse(
        raw_input=req.raw_input,
        normalized=text,
        is_valid=bool(fund_name),
        fund_name=fund_name,
        fund_type=fund_type,
        skip_prediction=skip_prediction,
        normalization_steps=["trim_whitespace", "remove_suffix_prefix", "left_pad_zeros", "validate_format_6_digits", "verify_danjuan"] if fund_name else ["trim_whitespace", "remove_suffix_prefix", "left_pad_zeros", "validate_format_6_digits", "verify_danjuan_failed"],
    ))


@router.get("/{code}/profile")
async def fund_profile(code: str, db=Depends(get_db)):
    try:
        profile = await fetch_profile(code, db)
        return ApiResponse(ok=True, data=profile)
    except ValueError as e:
        return ApiResponse(ok=False, error={"code": "PROFILE_NOT_FOUND", "message": str(e), "status": 404})
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "PROFILE_ERROR", "message": str(e), "status": 500})


@router.get("/{code}/news")
async def fund_news(code: str):
    return ApiResponse(ok=True, data={"message": "新闻功能开发中", "fund_code": code})


@router.post("/batch-predict")
async def batch_predict(req: FundBatchPredictRequest, db=Depends(get_db)):
    codes = req.fund_codes[:10]
    results = []
    errors = []
    for code in codes:
        try:
            pred = await do_predict(code, db)
            results.append(pred.model_dump())
        except Exception as e:
            errors.append({"fund_code": code, "error": str(e)})
    return ApiResponse(ok=True, data={"results": results, "errors": errors, "total": len(codes)})


@router.get("/{code}/backtest")
async def backtest(code: str, days: int = Query(90)):
    return ApiResponse(ok=True, data={"message": "回测功能开发中", "fund_code": code, "days": days})


@router.post("/{code}/rollback")
async def rollback_model_endpoint(code: str, req: FundRollbackRequest):
    ok = rollback_model(code, req.version)
    if not ok:
        return ApiResponse(ok=False, error={"code": "ROLLBACK_FAILED", "message": f"版本 {req.version} 不存在", "status": 404})
    return ApiResponse(ok=True, data={"message": f"已回滚到版本 {req.version}", "fund_code": code})