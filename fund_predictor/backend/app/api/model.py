from fastapi import APIRouter

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/health")
def health():
    return {"ok": True, "data": {"status": "ready"}}
