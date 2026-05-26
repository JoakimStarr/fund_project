from app.core.config import settings


def get_limit(fund_type: str) -> float:
    limits = settings.nav_constraints
    return limits.get(fund_type)


def apply_constraints(fund_type: str, predicted_return: float) -> tuple:
    limit = get_limit(fund_type)
    if limit is None:
        return predicted_return, False, 0.0
    clipped = max(-limit, min(predicted_return, limit))
    is_clipped = abs(clipped - predicted_return) > 1e-8
    return clipped, is_clipped, limit