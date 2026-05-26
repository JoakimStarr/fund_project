from fastapi import APIRouter

from app.api.fund import router as fund_router
from app.api.train import router as train_router
from app.api.task import router as task_router
from app.api.intraday import router as intraday_router
from app.api.ai_analysis import router as ai_analysis_router
from app.api.dashboard import router as dashboard_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(fund_router)
api_router.include_router(train_router)
api_router.include_router(task_router)
api_router.include_router(intraday_router)
api_router.include_router(ai_analysis_router)
api_router.include_router(dashboard_router)
api_router.include_router(admin_router)