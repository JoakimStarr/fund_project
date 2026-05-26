from fastapi import APIRouter, Query

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/fund", tags=["fund"])


@router.post("/predict")
async def predict() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/search")
async def search_funds(q: str = Query(...)) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.post("/validate")
async def validate_fund() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/{code}/profile")
async def fund_profile(code: str) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/{code}/news")
async def fund_news(code: str) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.post("/batch-predict")
async def batch_predict() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/{code}/backtest")
async def backtest(code: str, days: int = Query(90)) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.post("/{code}/rollback")
async def rollback_model(code: str) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})