from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/recent-predictions")
async def recent_predictions() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})