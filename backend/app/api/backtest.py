from fastapi import APIRouter, Query

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/{code}")
async def run_backtest(code: str, days: int = Query(90)) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})