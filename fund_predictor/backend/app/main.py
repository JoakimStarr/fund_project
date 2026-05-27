from fastapi import FastAPI
from app.core.database import init_db
from app.core.middleware import setup_middleware
from app.core.errors import AppError, app_error_handler, general_error_handler
from app.core.scheduler import init_scheduler
from app.api.router import api_router

app = FastAPI(title="FundPredictor", version="1.0.0")

setup_middleware(app)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, general_error_handler)
app.include_router(api_router, prefix="/api/v1")
init_scheduler(app)

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/health")
async def health():
    return {"ok": True, "data": {"status": "healthy", "version": "1.0.0"}}