from fastapi import APIRouter, Query

from app.core.errors import AppError
from app.services.task_service import get_task, get_tasks_history

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("")
def task_list(
    fund_code: str | None = Query(None, description="筛选特定基金的任务"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数上限"),
):
    """获取历史训练任务列表"""
    tasks = get_tasks_history(limit=limit, fund_code=fund_code)
    return {"ok": True, "data": tasks}


@router.get("/{task_id}")
def task_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise AppError("训练任务不存在", stage="task_lookup", details={"task_id": task_id})
    return {"ok": True, "data": task}
