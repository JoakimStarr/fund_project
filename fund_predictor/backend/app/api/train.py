from fastapi import APIRouter, BackgroundTasks

from app.core.logging_config import set_log_context
from app.schemas.fund import TrainRequest
from app.services.task_service import create_task, run_training_task

router = APIRouter(prefix="/api/train", tags=["train"])


@router.post("")
def train(req: TrainRequest, background_tasks: BackgroundTasks):
    fund_code = req.fund_code.strip()
    task_id = create_task(fund_code)
    set_log_context(fund_code=fund_code, task_id=task_id)
    background_tasks.add_task(run_training_task, task_id, fund_code, req.force)
    return {"ok": True, "task_id": task_id, "status": "running"}
