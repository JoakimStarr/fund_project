from app.core.config import settings


def should_use_group_model(fund_code: str, history_days: int) -> dict:
    threshold = settings.cold_start["threshold_days"]
    blend_start = settings.cold_start["blend_start_days"]
    blend_end = settings.cold_start["blend_end_days"]
    if history_days < threshold:
        return {"use_group": True, "strategy": "pure_group", "blend_ratio": 0.0}
    if history_days < blend_end:
        blend_ratio = (history_days - blend_start) / (blend_end - blend_start)
        return {"use_group": True, "strategy": "blended", "blend_ratio": round(blend_ratio, 4)}
    return {"use_group": False, "strategy": "individual", "blend_ratio": 1.0}