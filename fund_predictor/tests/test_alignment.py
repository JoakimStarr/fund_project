import numpy as np
import pandas as pd
import pytest
from backend.app.services.model_selection_service import _align_predictions, AlignmentResult


class TestAlignmentPerfectMatch:
    """Level 0: 完美匹配场景"""
    
    def test_exact_length_match(self):
        predictions = np.array([0.6, 0.7, 0.4, 0.8, 0.3])
        target_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "target_next": [0.01, -0.02, 0.03, -0.01, 0.02]
        })
        
        result = _align_predictions(predictions, target_df)
        
        assert isinstance(result, AlignmentResult)
        assert result.strategy_used == "perfect_match"
        assert not result.is_degraded
        assert len(result.aligned_predictions) == 5
        np.testing.assert_array_equal(result.aligned_predictions, predictions)
    
    def test_empty_arrays(self):
        predictions = np.array([])
        target_df = pd.DataFrame({"date": [], "target_next": []})
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "perfect_match"
        assert len(result.aligned_predictions) == 0


class TestAlignmentDateIndex:
    """Level 1: 日期索引对齐场景"""
    
    def test_date_alignment_success(self):
        predictions = np.array([0.6, 0.7, 0.4])
        source_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-03", "2024-01-05"],
            "feature": [1, 2, 3]
        })
        target_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-03", "2024-01-05"],
            "target_next": [0.01, 0.02, -0.01]
        })
        
        result = _align_predictions(predictions, target_df, source_df)
        
        assert result.strategy_used == "date_index"
        assert not result.is_degraded
        assert len(result.aligned_predictions) == 3
    
    def test_date_alignment_partial_missing(self):
        predictions = np.array([0.6, 0.7, 0.4, 0.8])
        source_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "feature": [1, 2, 3, 4]
        })
        # 目标 DF 有一个日期不在源中（缺失率 < 20%）
        target_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-06"],  # 最后一个日期不匹配
            "target_next": [0.01, 0.02, -0.01, 0.03]
        })
        
        result = _align_predictions(predictions, target_df, source_df)
        
        assert "date_index" in result.strategy_used
        assert result.is_degraded
        assert np.isnan(result.aligned_predictions[3])  # 缺失的日期应该是 NaN


class TestAlignmentTruncation:
    """Level 2: 智能截断场景"""
    
    def test_truncate_longer_predictions(self):
        predictions = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])  # 8 个值
        target_df = pd.DataFrame({
            "date": ["2024-01-0{}".format(i) for i in range(1, 6)],
            "target_next": [0.01] * 5
        })  # 5 行
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "truncation"
        assert result.is_degraded
        assert len(result.aligned_predictions) == 5
        # 应该取最后 5 个值（最新的）
        np.testing.assert_array_equal(result.aligned_predictions, np.array([0.4, 0.5, 0.6, 0.7, 0.8]))
    
    def test_truncate_preserves_recent_data(self):
        old_predictions = np.array([0.1, 0.2, 0.3])
        recent_predictions = np.array([0.7, 0.8, 0.9, 0.95, 0.99])
        all_predictions = np.concatenate([old_predictions, recent_predictions])
        
        target_df = pd.DataFrame({
            "date": ["2024-01-0{}".format(i) for i in range(1, 6)],
            "target_next": [0.01] * 5
        })
        
        result = _align_predictions(all_predictions, target_df)
        
        np.testing.assert_array_almost_equal(result.aligned_predictions, recent_predictions)


class TestAlignmentPadding:
    """Level 3: 安全填充场景"""
    
    def test_pad_shorter_predictions(self):
        predictions = np.array([0.6, 0.7, 0.8])  # 只有 3 个值
        target_df = pd.DataFrame({
            "date": ["2024-01-0{}".format(i) for i in range(1, 6)],
            "target_next": [0.01] * 5
        })  # 需要 5 个值
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "padding"
        assert result.is_degraded
        assert len(result.aligned_predictions) == 5
        # 前 2 个应该是 NaN，后 3 个是预测值
        assert np.isnan(result.aligned_predictions[0])
        assert np.isnan(result.aligned_predictions[1])
        np.testing.assert_array_almost_equal(result.aligned_predictions[2:], predictions)
    
    def test_insufficient_data_fails(self):
        predictions = np.array([0.6])  # 只有 1 个值
        target_df = pd.DataFrame({
            "date": ["2024-01-0{}".format(i) for i in range(1, 11)],
            "target_next": [0.01] * 10
        })  # 需要 10 个值 (50% = 5, 但只有 1)
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "failed"
        assert len(result.aligned_predictions) == 0


class TestAlignmentEdgeCases:
    """边界情况和特殊场景"""
    
    def test_single_element_match(self):
        predictions = np.array([0.5])
        target_df = pd.DataFrame({
            "date": ["2024-01-01"],
            "target_next": [0.01]
        })
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "perfect_match"
        assert not result.is_degraded
    
    def test_large_dataset_truncation(self):
        predictions = np.random.rand(1000)
        target_df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=800),
            "target_next": np.random.randn(800) * 0.02
        })
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "truncation"
        assert len(result.aligned_predictions) == 800
    
    def test_with_nan_in_predictions(self):
        predictions = np.array([0.6, np.nan, 0.8, 0.4])
        target_df = pd.DataFrame({
            "date": ["2024-01-0{}".format(i) for i in range(1, 5)],
            "target_next": [0.01] * 4
        })
        
        result = _align_predictions(predictions, target_df)
        
        assert result.strategy_used == "perfect_match"
        assert len(result.aligned_predictions) == 4
        assert np.isnan(result.aligned_predictions[1])


class TestFundCodeLogging:
    """验证基金代码在日志中的传递"""
    
    def test_fund_code_in_result(self, caplog):
        predictions = np.array([0.6, 0.7])
        target_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "target_next": [0.01, -0.01]
        })
        
        result = _align_predictions(predictions, target_df, fund_code="110011")
        
        assert result.strategy_used == "perfect_match"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
