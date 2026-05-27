from fastapi import APIRouter

router = APIRouter()

@router.get("/data-status")
async def data_status():
    return {"ok": True, "data": {"message": "not implemented"}}

@router.delete("/cache/{fund_code}")
async def clear_cache(fund_code: str):
    return {"ok": True, "data": {"fund_code": fund_code, "cache_cleared": False}}