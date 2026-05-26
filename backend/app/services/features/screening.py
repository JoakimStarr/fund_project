import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def spearman_ic(features_df: pd.DataFrame, target_series: pd.Series) -> dict:
    ic_values = {}
    for col in features_df.columns:
        common = features_df[col].dropna().index.intersection(target_series.dropna().index)
        if len(common) < 10:
            ic_values[col] = 0.0
        else:
            corr, _ = spearmanr(features_df[col].loc[common], target_series.loc[common])
            ic_values[col] = corr if not np.isnan(corr) else 0.0
    return ic_values


def vif_clustering(features_df: pd.DataFrame, corr_threshold: float = 0.8) -> list:
    corr_matrix = features_df.corr().abs()
    remaining = list(features_df.columns)
    clusters = []
    while remaining:
        seed = remaining[0]
        cluster = [seed]
        for col in remaining[1:]:
            if col in corr_matrix.columns and seed in corr_matrix.index:
                if corr_matrix.loc[seed, col] > corr_threshold:
                    cluster.append(col)
        for c in cluster:
            if c in remaining:
                remaining.remove(c)
        clusters.append(cluster)
    return clusters


def screen_features(features_df: pd.DataFrame, target_series: pd.Series, ic_threshold: float = 0.02, vif_threshold: float = 10.0) -> list:
    ic_values = spearman_ic(features_df, target_series)
    selected = [col for col in features_df.columns if abs(ic_values.get(col, 0)) >= ic_threshold]
    if not selected:
        selected = list(features_df.columns)
    clusters = vif_clustering(features_df[selected])
    final_selected = []
    for cluster in clusters:
        best = max(cluster, key=lambda c: abs(ic_values.get(c, 0)))
        final_selected.append(best)
    return final_selected