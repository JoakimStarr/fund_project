from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(task_id: str) -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})


@router.get("/")
async def list_tasks() -> ApiResponse:
    return ApiResponse(ok=True, data={"message": "not implemented yet"})