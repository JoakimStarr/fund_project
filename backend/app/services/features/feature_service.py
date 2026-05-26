import logging
import pandas as pd
import numpy as np
from app.services.features.technical import compute_all as compute_technical
from app.services.features.benchmark import calc_beta, calc_tracking_error, calc_alpha
from app.services.features.equity_features import calc_style_exposure
from app.services.features.bond_features import calc_duration_impact, calc_term_spread
from app.services.features.macro_features import calc_north_flow_impact, calc_exchange_rate_impact, calc_shibor_impact
from app.services.features.calendar import get_calendar_features
from app.services.features.screening import screen_features

logger = logging.getLogger(__name__)


def build_features(fund_code: str, nav_data: list, fund_type: str, holdings=None, macro_data=None) -> pd.DataFrame:
    if not nav_data:
        raise ValueError("NAV 数据为空")
    df = pd.DataFrame(nav_data)
    df["nav_date"] = pd.to_datetime(df["nav_date"])
    df = df.sort_values("nav_date").reset_index(drop=True)
    nav_series = df.set_index("nav_date")["nav"]
    all_features = {}
    tech_features = compute_technical(df)
    all_features.update(tech_features)
    if not nav_series.empty:
        cal_features = get_calendar_features(nav_series.index[-1])
        all_features.update(cal_features)
    if fund_type in ("index_equity", "index_bond", "equity_active", "hybrid_equity") and macro_data:
        north = calc_north_flow_impact(macro_data.get("north_flow", pd.DataFrame()))
        fx = calc_exchange_rate_impact(macro_data.get("exchange_rate", pd.DataFrame()))
        shibor = calc_shibor_impact(macro_data.get("shibor", pd.DataFrame()))
        all_features.update(north)
        all_features.update(fx)
        all_features.update(shibor)
    result_df = pd.DataFrame([all_features])
    result_df = result_df.replace([float("inf"), float("-inf")], float("nan"))
    return result_df


def build_and_screen(fund_code: str, nav_data: list, fund_type: str, target_col: str = "daily_return", holdings=None, macro_data=None) -> tuple:
    features = build_features(fund_code, nav_data, fund_type, holdings, macro_data)
    if not nav_data:
        return features, []
    nav_df = pd.DataFrame(nav_data)
    target = nav_df[target_col].dropna()
    if target.empty:
        return features, list(features.columns)
    selected = screen_features(features, target)
    return features, selected