import asyncio
from fastapi import APIRouter, Query, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.fund import FundPredictRequest, FundValidateRequest, FundValidateResponse, FundBatchPredictRequest, FundRollbackRequest, FundSearchResult
from app.services.fund.normalizer import normalize as normalize_fund_code
from app.services.fund.profile_service import get_profile as fetch_profile
from app.services.predict.prediction_service import predict as do_predict
from app.services.model.versioning import rollback as rollback_model

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
        import akshare as ak
        df = ak.fund_open_fund_search_em(symbol=q)
        if df is None or df.empty:
            return ApiResponse(ok=True, data=[])
        results = []
        for _, row in df.head(20).iterrows():
            results.append(FundSearchResult(
                fund_code=str(row.get("基金代码", "")),
                fund_name=str(row.get("基金简称", "")),
                fund_type_raw=str(row.get("基金类型", "")) if "基金类型" in row else None,
                company=str(row.get("基金公司", "")) if "基金公司" in row else None,
            ))
        return ApiResponse(ok=True, data=results)
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "SEARCH_ERROR", "message": str(e), "status": 500})


@router.post("/validate")
async def validate_fund(req: FundValidateRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, normalize_fund_code, req.raw_input)
    return ApiResponse(ok=True, data=FundValidateResponse(**result))


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