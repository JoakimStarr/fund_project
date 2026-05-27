from fastapi import APIRouter
from app.api import fund, train, task, backtest, intraday, ai_analysis, dashboard, admin

api_router = APIRouter()

api_router.include_router(fund.router, prefix="/fund", tags=["fund"])
api_router.include_router(train.router, prefix="/train", tags=["train"])
api_router.include_router(task.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(backtest.router, prefix="/fund", tags=["backtest"])
api_router.include_router(intraday.router, prefix="/intraday", tags=["intraday"])
api_router.include_router(ai_analysis.router, prefix="/ai", tags=["ai"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])