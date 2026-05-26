import pandas as pd


def get_calendar_features(date) -> dict:
    if isinstance(date, str):
        date = pd.Timestamp(date)
    return {
        "is_month_end": int(date.is_month_end),
        "is_quarter_end": int(date.is_quarter_end),
        "is_month_start": int(date.is_month_start),
        "is_monday": int(date.dayofweek == 0),
        "is_friday": int(date.dayofweek == 4),
    }