from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/model", tags=["model"])


@router.get("/health")
def health():
    return {"ok": True, "data": {"status": "ready"}}
