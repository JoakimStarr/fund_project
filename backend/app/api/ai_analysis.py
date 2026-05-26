from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analysis")
async def ai_analysis() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/provider-status")
async def provider_status() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})