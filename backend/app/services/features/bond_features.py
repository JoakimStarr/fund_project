import numpy as np


def calc_duration_impact(duration: float, yield_change: float) -> float:
    return -duration * yield_change


def calc_term_spread(long_yield: float, short_yield: float) -> float:
    return long_yield - short_yield


def calc_dr007_level(dr007: float) -> float:
    return dr007