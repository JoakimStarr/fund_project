from fastapi import APIRouter

from backend.app.core.errors import AppError
from backend.app.services.task_service import get_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}")
def task_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise AppError("训练任务不存在", stage="task_lookup", details={"task_id": task_id})
    return {"ok": True, "data": task}
