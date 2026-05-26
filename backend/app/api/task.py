from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.task.task_service import get_task_status, list_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str, db=Depends(get_db)):
    data = await get_task_status(task_id, db)
    if data is None:
        return ApiResponse(ok=False, error={"code": "TASK_NOT_FOUND", "message": f"任务 {task_id} 不存在", "status": 404})
    return ApiResponse(ok=True, data=data)


@router.get("/")
async def list_tasks_api(fund_code: str = None, limit: int = 20, offset: int = 0, db=Depends(get_db)):
    tasks = await list_tasks(db, fund_code=fund_code, limit=limit, offset=offset)
    return ApiResponse(ok=True, data={"tasks": tasks, "total": len(tasks)})