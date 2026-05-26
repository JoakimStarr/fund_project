from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.train import TrainRequest, TrainTaskResponse
from app.services.task.task_service import enqueue_train, get_task_status, list_tasks

router = APIRouter(prefix="/train", tags=["train"])


@router.post("/")
async def create_train_task(req: TrainRequest, db=Depends(get_db)):
    result = await enqueue_train(req.fund_code, db, force_retrain=req.force_retrain)
    return ApiResponse(ok=True, data=TrainTaskResponse(**result))