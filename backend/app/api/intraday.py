from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/intraday", tags=["intraday"])


@router.post("/{code}")
async def intraday_estimate(code: str) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})