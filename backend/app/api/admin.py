import asyncio
from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from sqlalchemy import select, func
from app.models.fund_nav import FundNav
from app.models.fund_profile import FundProfileCache
from app.models.data_status import DataStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/data-status")
async def data_status_api(db=Depends(get_db)):
    status_list = []

    nav_result = await db.execute(
        select(func.count(FundNav.id), func.max(FundNav.nav_date))
    )
    nav_count, nav_max = nav_result.one()
    status_list.append({
        "data_type": "fund_nav",
        "identifier": "all",
        "row_count": nav_count or 0,
        "latest_date": str(nav_max) if nav_max else None,
        "status": "ok" if (nav_count or 0) > 0 else "empty",
    })

    profile_result = await db.execute(
        select(func.count(FundProfileCache.fund_code))
    )
    profile_count = profile_result.scalar() or 0
    status_list.append({
        "data_type": "fund_profile",
        "identifier": "all",
        "row_count": profile_count,
        "latest_date": None,
        "status": "ok" if profile_count > 0 else "empty",
    })

    ds_result = await db.execute(select(DataStatus).order_by(DataStatus.last_updated.desc()))
    ds_rows = ds_result.scalars().all()
    for ds in ds_rows:
        status_list.append({
            "data_type": ds.data_type,
            "identifier": ds.identifier,
            "row_count": ds.row_count,
            "latest_date": ds.latest_date,
            "last_updated": ds.last_updated.isoformat() if ds.last_updated else None,
            "status": ds.status,
        })

    return ApiResponse(ok=True, data={"items": status_list, "total": len(status_list)})


@router.post("/update-data")
async def update_data_api(db=Depends(get_db)):
    tasks = []

    try:
        from app.services.data.nav_service import fetch_and_store_nav
        from app.services.data.index_service import fetch_all_indices

        result = await db.execute(select(FundProfileCache.fund_code))
        fund_codes = [r[0] for r in result.all()]
        if not fund_codes:
            return ApiResponse(ok=True, data={"message": "无已注册基金，请先在基金画像页面添加基金", "tasks": []})

        for code in fund_codes[:5]:
            try:
                await fetch_and_store_nav(code)
                tasks.append({"fund_code": code, "status": "success"})
            except Exception as e:
                tasks.append({"fund_code": code, "status": "failed", "error": str(e)})

        try:
            await fetch_all_indices()
            tasks.append({"type": "index_data", "status": "success"})
        except Exception as e:
            tasks.append({"type": "index_data", "status": "failed", "error": str(e)})

        return ApiResponse(ok=True, data={
            "message": f"已完成 {len([t for t in tasks if t['status'] == 'success'])}/{len(tasks)} 个任务",
            "tasks": tasks,
        })
    except Exception as e:
        return ApiResponse(ok=False, error={"code": "UPDATE_ERROR", "message": str(e), "status": 500})