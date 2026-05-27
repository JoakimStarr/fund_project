from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

def init_scheduler(app):
    @app.on_event("startup")
    async def start_scheduler():
        scheduler.start()
    
    @app.on_event("shutdown")
    async def shutdown_scheduler():
        scheduler.shutdown(wait=True)