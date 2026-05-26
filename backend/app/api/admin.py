from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/data-status")
async def data_status() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.post("/update-data")
async def update_data() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})