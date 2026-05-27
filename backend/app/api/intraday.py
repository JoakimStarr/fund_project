from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.predict.intraday_service import estimate_t_day

router = APIRouter(prefix="/intraday", tags=["intraday"])


@router.post("/{code}")
async def intraday_estimate(code: str, db=Depends(get_db)):
    try:
        result = await estimate_t_day(code, session=db, mode="intraday", save_result=False)
        return ApiResponse(ok=True, data=result)
    except ValueError as e:
        return ApiResponse(ok=False, error={"code": "INTRADAY_ERROR", "message": str(e), "status": 422})
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "INTRADAY_ERROR", "message": str(e), "status": 500})


@router.post("/{code}/save")
async def intraday_save_estimate(code: str, db=Depends(get_db)):
    try:
        result = await estimate_t_day(code, session=db, mode="closing", save_result=True)
        return ApiResponse(ok=True, data={"saved": True, **result})
    except ValueError as e:
        return ApiResponse(ok=False, error={"code": "INTRADAY_ERROR", "message": str(e), "status": 422})
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "INTRADAY_ERROR", "message": str(e), "status": 500})
