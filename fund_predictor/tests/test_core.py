"""
核心单元测试：验证阶段0和阶段1的关键改动。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pandas as pd
import pytest


class TestFactorScreening:
    """因子预筛选模块测试"""

    def test_ic_filtering(self):
        from app.services.features.factor_screening import pre_screen_factors, FactorScreeningResult
        
        np.random.seed(42)
        n = 200
        df = pd.DataFrame({
            "good_feature": np.random.randn(n) * 0.1 + np.linspace(-1, 1, n),
            "noise_feature": np.random.randn(n),
            "target_next": np.linspace(-0.02, 0.02, n) + np.random.randn(n) * 0.01,
        })
        
        result = pre_screen_factors(
            df, 
            feature_cols=["good_feature", "noise_feature"],
            target_col="target_next",
            ic_threshold=0.05,
        )
        
        assert isinstance(result, FactorScreeningResult)
        assert len(result.screened_features) >= 1
        assert "good_feature" in result.screened_features or result.screened_features == []

    def test_vif_removal(self):
        from app.services.features.factor_screening import pre_screen_factors, FactorScreeningResult
        
        n = 200
        base = np.random.randn(n)
        df = pd.DataFrame({
            "feature_a": base,
            "feature_b": base * 2 + np.random.randn(n) * 0.01,
            "feature_c": np.random.randn(n),
            "target_next": base * 0.3 + np.random.randn(n) * 0.5,
        })
        
        result = pre_screen_factors(
            df,
            feature_cols=["feature_a", "feature_b", "feature_c"],
            target_col="target_next",
            vif_threshold=5.0,
        )
        
        assert isinstance(result, FactorScreeningResult)

    def test_insufficient_data_fallback(self):
        from app.services.features.factor_screening import pre_screen_factors
        
        df = pd.DataFrame({
            "f1": [1, 2, 3],
            "target_next": [0.01, -0.01, 0.005],
        })
        
        result = pre_screen_factors(df, ["f1"], ic_threshold=0.1)
        assert result.screened_features == ["f1"]
        assert result.removed_features == []


class TestFourWaySplit:
    """四段数据划分测试"""

    def test_split_returns_four_parts(self):
        from app.services.model_selection_service import _split_train_valid_test
        
        df = pd.DataFrame({"a": range(100), "target_next": np.random.randn(100)})
        parts = _split_train_valid_test(df)
        
        assert len(parts) == 4
        assert all(len(p) > 0 for p in parts)
        total = sum(len(p) for p in parts)
        assert total <= len(df)

    def test_split_order_preserved(self):
        from app.services.model_selection_service import _split_train_valid_test
        
        df = pd.DataFrame({"a": range(100)})
        parts = _split_train_valid_test(df)
        
        train, valid, test_sel, test_final = parts
        assert train.index.max() < valid.index.min()
        assert valid.index.max() < test_sel.index.min()
        assert test_sel.index.max() < test_final.index.min()

    def test_split_proportions(self):
        from app.services.model_selection_service import _split_train_valid_test
        
        df = pd.DataFrame({"a": range(1000)})
        parts = _split_train_valid_test(df)
        
        ratios = [len(p)/1000 for p in parts]
        assert 0.50 < ratios[0] < 0.60   # ~55% train
        assert 0.18 < ratios[1] < 0.26   # ~22% valid
        assert 0.10 < ratios[2] < 0.16   # ~13% test_select
        assert 0.07 < ratios[3] < 0.13   # ~10% test_final


class TestFundProfileService:
    """基金画像解析测试"""

    def test_classify_fund_returns_profile(self):
        from app.services.fund_profile_service import classify_fund, FundProfile
        
        profile = classify_fund("018956")
        assert isinstance(profile, FundProfile)
        assert profile.fund_code == "018956"
        assert profile.fund_type in [
            "hybrid_equity", "equity_active", "bond_pure",
            "index_equity", "money_market", "unknown"
        ]

    def test_classification_types(self):
        from app.services.fund_profile_service import _classify_by_type
        
        assert _classify_by_type("混合型-偏股") == "hybrid_equity"
        assert _classify_by_type("股票型") == "equity_active"
        assert _classify_by_type("货币型") == "money_market"
        assert _classify_by_type("债券型-纯债") == "bond_pure"
        assert _classify_by_type("指数型-股票") == "index_equity"

    def test_size_parsing(self):
        from app.services.fund_profile_service import _parse_size
        
        assert abs(_parse_size("15.23亿") - 15.23) < 0.001
        assert abs(_parse_size("100") - 100.0) < 0.001
        assert _parse_size(None) is None


class TestRoutingService:
    """分类路由引擎测试"""

    def test_money_market_skips_prediction(self):
        from app.services.routing_service import route_predict
        from app.services.fund_profile_service import FundProfile
        
        profile = FundProfile(
            fund_code="000000",
            fund_type="money_market",
            skip_prediction=True,
        )
        result = route_predict("000000", profile, "test-req-id")
        assert result["fund_type"] == "money_market"
        assert "净值恒为1" in result.get("message", "")


class TestHTTPStatusCodes:
    """异常HTTP状态码映射测试"""

    def test_data_fetch_error_status(self):
        from app.core.errors import DataFetchError
        
        err = DataFetchError("test")
        assert err.http_status == 502

    def test_model_not_found_status(self):
        from app.core.errors import ModelNotFoundError
        
        err = ModelNotFoundError("test")
        assert err.http_status == 404

    def test_insufficient_data_status(self):
        from app.core.errors import InsufficientDataError
        
        err = InsufficientDataError("test")
        assert err.http_status == 422

    def test_default_status_400(self):
        from app.core.errors import FeatureBuildError
        
        err = FeatureBuildError("test")
        assert err.http_status == 400


class TestConformalPrediction:
    """保形预测测试"""

    def test_conformal_interval_coverage(self):
        from app.services.postprocessing.conformal import conformal_interval
        
        from sklearn.linear_model import Ridge
        
        np.random.seed(123)
        n_calib = 100
        X_calib = pd.DataFrame({
            "f1": np.random.randn(n_calib),
            "f2": np.random.randn(n_calib),
        })
        y_calib = X_calib["f1"] * 0.5 + X_calib["f2"] * 0.3 + np.random.randn(n_calib) * 0.1
        
        model = Ridge(alpha=1.0)
        model.fit(X_calib[["f1", "f2"]], y_calib)
        
        X_new = pd.DataFrame({
            "f1": [1.0, -1.0, 0.0],
            "f2": [0.5, -0.5, 0.0],
        })
        
        lower, upper, meta = conformal_interval(
            model, X_calib, y_calib, X_new,
            alpha=0.10, feature_cols=["f1", "f2"],
        )
        
        assert len(lower) == 3
        assert len(upper) == 3
        assert all(lower <= upper)
        assert meta["method"] == "conformal_quantile"
        assert meta["expected_coverage"] == 0.90

    def test_small_calibration_fallback(self):
        from app.services.postprocessing.conformal import conformal_interval
        
        from sklearn.linear_model import Ridge
        
        model = Ridge(alpha=1.0)
        model.fit([[1]], [0])
        
        X_calib = pd.DataFrame({"f1": [1, 2]})
        y_calib = np.array([0.1, 0.2])
        X_new = pd.DataFrame({"f1": [1.5]})
        
        lower, upper, meta = conformal_interval(
            model, X_calib, y_calib, X_new,
            alpha=0.10, feature_cols=["f1"],
        )
        
        assert "fallback" in meta["method"]


class TestNavConstraints:
    """预测值约束规则测试"""

    def test_equity_constraint_clipping(self):
        from app.services.postprocessing.constraints import apply_nav_constraints
        
        result = apply_nav_constraints(0.25, "hybrid_equity")
        assert result.is_clipped is True
        assert result.constrained_return == 0.20

    def test_normal_value_no_clip(self):
        from app.services.postprocessing.constraints import apply_nav_constraints
        
        result = apply_nav_constraints(0.01, "hybrid_equity")
        assert result.is_clipped is False
        assert abs(result.constrained_return - 0.01) < 1e-8

    def test_bond_stricter_limit(self):
        from app.services.postprocessing.constraints import apply_nav_constraints
        
        result = apply_nav_constraints(0.08, "bond_pure")
        assert result.is_clipped is True
        assert result.constrained_return == 0.05

    def test_index_no_limit(self):
        from app.services.postprocessing.constraints import apply_nav_constraints
        
        result = apply_nav_constraints(0.30, "index_equity")
        assert result.is_clipped is False


class TestEnhancedEquityFeatures:
    """增强因子构建测试"""

    def test_build_enhanced_features_adds_columns(self):
        from app.services.features.enhanced_equity_features import build_enhanced_equity_features
        
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120)
        fund_ret = pd.Series(np.random.randn(120) * 0.01)
        df = pd.DataFrame({
            "date": dates,
            "nav": np.cumprod(1 + fund_ret),
            "acc_nav": np.cumprod(1 + np.random.randn(120) * 0.01),
            "daily_growth_pct": fund_ret * 100,
            "fund_ret": fund_ret,
            "fund_ret_lag1": fund_ret.shift(1),
            "fund_ret_lag2": fund_ret.shift(2),
            "hs300_ret": np.random.randn(120) * 0.012,
            "cyb_ret": np.random.randn(120) * 0.015,
            "zz500_ret": np.random.randn(120) * 0.013,
            "zz1000_ret": np.random.randn(120) * 0.016,
            "kcb50_ret": np.random.randn(120) * 0.017,
            "fund_ret_mom_5": fund_ret.rolling(5).sum(),
            "fund_ret_mom_20": fund_ret.rolling(20).sum(),
            "fund_ret_std_20": fund_ret.rolling(20).std(),
            "fund_ret_std_60": fund_ret.rolling(60).std(),
            "hs300_mom_5": df["hs300_ret"].rolling(5).sum() if False else np.random.randn(120) * 0.02,
            "style_growth_vs_large": np.random.randn(120) * 0.005,
            "style_small_vs_large": np.random.randn(120) * 0.004,
        })
        
        original_cols = set(df.columns)
        result = build_enhanced_equity_features(df)
        new_cols = set(result.columns) - original_cols
        
        assert len(new_cols) > 10, f"Expected many new columns, got {len(new_cols)}"
        assert "market_up_ratio" in new_cols
        assert "is_weekday_0" in new_cols
        assert "is_quarter_end" in new_cols


class TestStackingEnsemble:
    """Stacking集成模型测试"""

    def test_stacking_meta_learner_training(self):
        from app.services.features.ensemble import StackingEnsemble
        
        from sklearn.linear_model import Ridge, ElasticNet
        from sklearn.tree import DecisionTreeRegressor
        
        ensemble = StackingEnsemble(alpha=1.0)
        
        np.random.seed(99)
        n = 300
        X_train = pd.DataFrame({
            "f1": np.random.randn(n),
            "f2": np.random.randn(n),
            "f3": np.random.randn(n),
        })
        y_train = X_train["f1"] * 0.5 + X_train["f2"] * 0.3 + np.random.randn(n) * 0.1
        
        m1 = Ridge(alpha=1.0); m1.fit(X_train[["f1","f2","f3"]], y_train)
        m2 = ElasticNet(alpha=0.01); m2.fit(X_train[["f1","f2","f3"]], y_train)
        m3 = DecisionTreeRegressor(max_depth=3); m3.fit(X_train[["f1","f2","f3"]], y_train)
        ensemble.add_base_model("ridge", m1)
        ensemble.add_base_model("elastic", m2)
        ensemble.add_base_model("tree", m3)
        
        X_valid = pd.DataFrame({
            "f1": np.random.randn(60),
            "f2": np.random.randn(60),
            "f3": np.random.randn(60),
        })
        y_valid = X_valid["f1"] * 0.5 + X_valid["f2"] * 0.3 + np.random.randn(60) * 0.1
        
        metrics = ensemble.fit_meta_learner(X_valid, y_valid, ["f1", "f2", "f3"])
        
        assert metrics["status"] == "success"
        assert ensemble.fitted is True
        assert "model_weights" in metrics

    def test_stacking_prediction(self):
        from app.services.features.ensemble import StackingEnsemble
        
        from sklearn.linear_model import Ridge
        
        ensemble = StackingEnsemble(alpha=1.0)
        np.random.seed(42)
        n_train, n_valid = 50, 25
        X_all = pd.DataFrame({
            "f1": np.random.randn(n_train + n_valid),
            "f2": np.random.randn(n_train + n_valid),
        })
        y_all = X_all["f1"] * 0.5 + X_all["f2"] * 0.3 + np.random.randn(n_train + n_valid) * 0.05
        m = Ridge(alpha=1.0)
        m.fit(X_all.iloc[:n_train], y_all[:n_train])
        ensemble.add_base_model("ridge", m)
        
        metrics = ensemble.fit_meta_learner(
            X_all.iloc[n_train:], y_all[n_train:], ["f1", "f2"],
        )
        assert metrics["status"] == "success"
        
        X_new = pd.DataFrame({"f1": [0.5], "f2": [-0.3]})
        pred, meta = ensemble.predict(X_new, ["f1", "f2"])
        
        assert len(pred) == 1
        assert meta["method"] == "stacking_ridge"


class TestSampleWeights:
    """样本时间权重测试"""

    def test_exponential_decay_weights(self):
        from app.services.features.ensemble import build_sample_weights
        
        weights = build_sample_weights(180, halflife=60)
        
        assert len(weights) == 180
        assert abs(weights.sum() - 1.0) < 1e-6
        assert weights[-1] > weights[0]
        assert weights[119] < weights[179]

    def test_halflife_property(self):
        from app.services.features.ensemble import build_sample_weights
        
        w60 = build_sample_weights(120, halflife=60)
        w30 = build_sample_weights(120, halflife=30)
        
        assert w30[-1] > w60[-1]


class TestWalkForwardCV:
    """Walk-Forward交叉验证测试"""

    def test_walk_forward_basic(self):
        from app.services.features.ensemble import walk_forward_cv
        
        np.random.seed(77)
        n = 600
        df = pd.DataFrame({
            "date": pd.date_range("2022-01-01", periods=n),
            "f1": np.random.randn(n).cumsum() * 0.01,
            "f2": np.random.randn(n).cumsum() * 0.005,
            "target_next": np.random.randn(n) * 0.01,
        })
        
        results, agg = walk_forward_cv(
            df,
            feature_cols=["f1", "f2"],
            target_col="target_next",
            train_months=6,
            valid_months=1,
            step_months=1,
            min_rounds=3,
        )
        
        assert len(results) >= 3
        assert "mean_mae" in agg
        assert agg["mean_mae"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])