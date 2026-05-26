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
    tech_df = compute_technical(df)
    tech_df.index = nav_series.index
    cal_df = nav_series.to_frame("nav")
    cal_df["is_month_end"] = (cal_df.index.is_month_end).astype(int)
    cal_df["is_quarter_end"] = ((cal_df.index.month % 3 == 0) & (cal_df.index.is_month_end)).astype(int)
    cal_df["is_monday"] = (cal_df.index.dayofweek == 0).astype(int)
    cal_df["is_friday"] = (cal_df.index.dayofweek == 4).astype(int)
    feature_df = pd.concat([tech_df, cal_df[["is_month_end", "is_quarter_end", "is_monday", "is_friday"]]], axis=1)
    feature_df = feature_df.replace([float("inf"), float("-inf")], float("nan"))
    return feature_df


def build_and_screen(fund_code: str, nav_data: list, fund_type: str, target_col: str = "daily_return", holdings=None, macro_data=None) -> tuple:
    features = build_features(fund_code, nav_data, fund_type, holdings, macro_data)
    if not nav_data or len(nav_data) < 10:
        return features, []
    nav_df = pd.DataFrame(nav_data)
    nav_df["nav_date"] = pd.to_datetime(nav_df["nav_date"])
    target = nav_df.set_index("nav_date")[target_col].dropna()
    if target.empty:
        return features, []
    selected = screen_features(features, target)
    return features, selected