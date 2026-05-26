from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/train", tags=["train"])


@router.post("/")
async def create_train_task() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})