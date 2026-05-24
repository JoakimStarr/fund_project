"""
因子预筛选模块：IC检验、VIF共线性检测、因子衰减测试。
在进入模型训练前对所有候选因子做预筛选，剔除无效或冗余特征。
"""
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class FactorScreeningResult:
    """因子预筛选结果"""
    screened_features: list[str]
    removed_features: list[str]
    ic_report: dict[str, Any]
    vif_report: dict[str, Any]
    decay_report: dict[str, Any]
    screening_summary: dict[str, str]


def pre_screen_factors(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "target_next",
    ic_threshold: float = 0.02,
    vif_threshold: float = 10.0,
    icir_threshold: float = 0.5,
    decay_window: int = 20,
) -> FactorScreeningResult:
    """对候选因子进行预筛选
    
    筛选步骤：
    1. IC 检验：|Pearson IC| < ic_threshold 的因子排除
    2. VIF 检验：VIF > vif_threshold 的因子剔除（逐步回归式）
    3. ICIR 检验：IC均值/IC标准差 < icir_threshold 的因子排除
    4. 衰减测试：因子的预测有效期验证
    
    Args:
        df: 完整数据集（含特征和目标）
        feature_cols: 候选特征列名列表
        target_col: 目标列名
        ic_threshold: IC绝对值下限
        vif_threshold: VIF上限
        icir_threshold: ICIR稳定性下限
        decay_window: 衰减测试窗口
    
    Returns:
        FactorScreeningResult 包含筛选结果和详细报告
    """
    logger.info(
        "factor_pre_screen_start features=%d target=%s",
        len(feature_cols), target_col,
    )
    
    # 准备数据：去掉目标为NaN的行
    clean = df.dropna(subset=[target_col]).copy()
    
    if len(clean) < 50:
        logger.warning("factor_pre_screen_skipped reason=insufficient_data rows=%d", len(clean))
        return FactorScreeningResult(
            screened_features=feature_cols.copy(),
            removed_features=[],
            ic_report={},
            vif_report={},
            decay_report={},
            screening_summary={"reason": "insufficient_data"},
        )
    
    y = clean[target_col].to_numpy()
    
    # Step 1: IC 检验
    ic_results = {}
    for col in feature_cols:
        x = clean[col].dropna()
        if len(x) < 30:
            ic_results[col] = {"ic_mean": None, "ic_std": None, "icir": None}
            continue
        
        y_aligned = y[x.index]
        
        pearson_r, _ = stats.pearsonr(x.to_numpy(), y_aligned)
        spearman_rho, _ = stats.spearmanr(x.to_numpy(), y_aligned)
        
        ic_results[col] = {
            "ic_pearson": float(pearson_r),
            "ic_spearman": float(spearman_rho),
            "abs_ic_pearson": abs(float(pearson_r)),
        }
    
    # Step 2: VIF 检验（逐步回归式）
    remaining = [c for c in feature_cols if c in clean.columns]
    vif_removed = []
    vif_history = {}
    
    while remaining:
        X_vif = clean[remaining].dropna()
        if len(X_vif) < len(remaining) + 10:
            break
        
        try:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_vif)
            
            n = X_scaled.shape[1]
            vifs = {}
            for j in range(n):
                other_idx = [k for k in range(n) if k != j]
                if not other_idx:
                    continue
                X_others = X_scaled[:, other_idx]
                X_j = X_scaled[:, j]
                r2 = np.corrcoef(X_j, X_others @ np.linalg.lstsq(X_others, X_j, rcond=None)[0])[0, 1]**2
                vif_val = 1 / (1 - max(r2, 0)) if (1 - r2) > 0 else float('inf')
                vifs[remaining[j]] = round(vif_val, 2)
            
            worst_factor = max(vifs, key=vifs.get)
            worst_vif = vifs[worst_factor]
            vif_history[worst_factor] = worst_vif
            
            if worst_vif > vif_threshold:
                vif_removed.append(worst_factor)
                remaining.remove(worst_factor)
                logger.info(
                    "vif_removal factor=%s vif=%.1f threshold=%.1f",
                    worst_factor, worst_vif, vif_threshold,
                )
            else:
                break
        except Exception:
            break
    
    # Step 3: ICIR 计算（时间序列）
    icir_results = {}
    for col in remaining:
        x = clean[col].dropna()
        if len(x) < 60:
            icir_results[col] = None
            continue
        
        y_aligned = y[x.index]
        rolling_ics = []
        step = max(1, len(x) // 20)
        for i in range(60, len(x), step):
            window_x = x.iloc[i-60:i].to_numpy()
            window_y = y_aligned[i-60:i]
            r, _ = stats.pearsonr(window_x, window_y)
            rolling_ics.append(r)
        
        if len(rolling_ics) >= 5:
            ic_arr = np.array(rolling_ics)
            icir_results[col] = {
                "ic_mean": float(np.mean(ic_arr)),
                "ic_std": float(np.std(ic_arr)),
                "icir": float(np.mean(ic_arr)) / (float(np.std(ic_arr)) + 1e-8),
            }
        else:
            icir_results[col] = None
    
    # Step 4: 衰减测试
    decay_results = {}
    for col in remaining[:20]:  # 只对top20做衰减测试避免耗时过长
        x = clean[col].dropna()
        if len(x) < 100:
            decay_results[col] = None
            continue
        
        y_aligned = y[x.index]
        lags = [1, 3, 5, 10, 15, 20]
        lagged_ics = {}
        for lag in lags:
            valid_x = x.iloc[:-lag].to_numpy() if lag > 0 else x.to_numpy()
            valid_y = y_aligned[lag:] if lag > 0 else y_aligned
            if len(valid_x) > 30:
                r, _ = stats.pearsonr(valid_x, valid_y)
                lagged_ics[lag] = abs(float(r))
        
        decay_results[col] = {
            "lagged_ics": {str(k): v for k, v in lagged_ics.items()},
            "best_lag": min(lagged_ics, key=lagged_ics.get) if lagged_ics else None,
            "decay_rate": (
                (lagged_ics.get(1, 0) - lagged_ics.get(10, 0)) / (lagged_ics.get(1, 0) + 1e-8)
                if lagged_ics.get(1, 0) > 0 else None
            ),
        }
    
    # 综合筛选决策
    final_features = []
    removal_reasons = {}
    
    for col in remaining:
        reasons = []
        
        ic_info = ic_results.get(col, {})
        abs_ic = ic_info.get("abs_ic_pearson", 0) or 0
        if abs_ic < ic_threshold and col not in [
            "fund_ret_lag1", "fund_ret_lag2", "hs300_ret", "zz500_ret"
        ]:
            reasons.append(f"low_ic({abs_ic:.3f})")
        
        icir_info = icir_results.get(col)
        if icir_info is not None and icir_info.get("icir") is not None:
            if icir_info["icir"] < icir_threshold:
                reasons.append(f"low_icir({icir_info['icir']:.2f})")
        
        if not reasons:
            final_features.append(col)
        else:
            removal_reasons[col] = "; ".join(reasons)
    
    result = FactorScreeningResult(
        screened_features=final_features,
        removed_features=list(removal_reasons.keys()) + vif_removed,
        ic_report={
            factor: info for factor, info in ic_results.items()
        },
        vif_report=vif_history,
        decay_report={
            k: v for k, v in decay_results.items() if v is not None
        },
        screening_summary={
            "total_candidates": len(feature_cols),
            "screened_count": len(final_features),
            "removed_by_ic": len([r for r in removal_reasons.values() if "low_ic" in r]),
            "removed_by_icir": len([r for r in removal_reasons.values() if "low_icir" in r]),
            "removed_by_vif": len(vif_removed),
            "retention_rate": f"{len(final_features)/max(len(feature_cols),1)*100:.1f}%",
        },
    )
    
    logger.info(
        "factor_pre_screen_done total=%d screened=%d removed=%d retention=%s",
        len(feature_cols), len(final_features), len(result.removed_features),
        result.screening_summary["retention_rate"],
    )
    
    return result