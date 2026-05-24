from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.get("/health")
def health():
    return {"ok": True, "data": {"status": "ready"}}
