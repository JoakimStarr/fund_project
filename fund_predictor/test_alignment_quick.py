#!/usr/bin/env python3
"""快速验证 _align_predictions 函数的各个场景"""
import sys
sys.path.insert(0, '/home/joakim/Project/fund_project/fund_predictor/backend')

import numpy as np
import pandas as pd
from app.services.model_selection_service import _align_predictions, AlignmentResult


def test_scenario(name, predictions, target_df, source_df=None, expected_strategy=None, expect_degraded=None):
    print(f"\n{'='*60}")
    print(f"测试场景: {name}")
    print(f"{'='*60}")
    print(f"预测值长度: {len(predictions)}")
    print(f"目标 DF 长度: {len(target_df)}")
    
    result = _align_predictions(predictions, target_df, source_df)
    
    print(f"✅ 对齐策略: {result.strategy_used}")
    print(f"   是否降级: {result.is_degraded}")
    print(f"   结果长度: {len(result.aligned_predictions)}")
    
    if expected_strategy and result.strategy_used != expected_strategy:
        print(f"❌ 期望策略: {expected_strategy}, 实际: {result.strategy_used}")
        return False
    
    if expect_degraded is not None and result.is_degraded != expect_degraded:
        print(f"❌ 期望降级: {expect_degraded}, 实际: {result.is_degraded}")
        return False
    
    if len(result.aligned_predictions) == 0 and result.strategy_used == "failed":
        print(f"⚠️  对齐失败: {result.degradation_reason}")
    else:
        print(f"   前3个值: {result.aligned_predictions[:3]}")
    
    print("✅ 通过")
    return True


def main():
    all_passed = True
    
    # 场景 1: 完美匹配
    all_passed &= test_scenario(
        "Level 0 - 完美匹配 (长度相同)",
        predictions=np.array([0.6, 0.7, 0.4, 0.8, 0.3]),
        target_df=pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "target_next": [0.01, -0.02, 0.03, -0.01, 0.02]
        }),
        expected_strategy="perfect_match",
        expect_degraded=False
    )
    
    # 场景 2: 需要截断（预测值过多）
    all_passed &= test_scenario(
        "Level 2 - 智能截断 (预测值 > 目标长度)",
        predictions=np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]),  # 8 个
        target_df=pd.DataFrame({
            "date": [f"2024-01-0{i}" for i in range(1, 6)],
            "target_next": [0.01] * 5
        }),  # 5 个
        expected_strategy="truncation",
        expect_degraded=True
    )
    
    # 场景 3: 需要填充（预测值过少）
    all_passed &= test_scenario(
        "Level 3 - 安全填充 (预测值 < 目标长度)",
        predictions=np.array([0.6, 0.7, 0.8]),  # 3 个
        target_df=pd.DataFrame({
            "date": [f"2024-01-0{i}" for i in range(1, 6)],
            "target_next": [0.01] * 5
        }),  # 5 个
        expected_strategy="padding",
        expect_degraded=True
    )
    
    # 场景 4: 数据严重不足
    all_passed &= test_scenario(
        "Level 4 - 数据不足导致失败",
        predictions=np.array([0.6]),  # 只有 1 个
        target_df=pd.DataFrame({
            "date": [f"2024-01-{str(i).zfill(2)}" for i in range(1, 11)],
            "target_next": [0.01] * 10
        }),  # 需要 10 个
        expected_strategy="failed"
    )
    
    # 场景 5: 日期索引对齐
    all_passed &= test_scenario(
        "Level 1 - 日期索引对齐",
        predictions=np.array([0.6, 0.7, 0.4]),
        source_df=pd.DataFrame({
            "date": ["2024-01-01", "2024-01-03", "2024-01-05"],
            "feature": [1, 2, 3]
        }),
        target_df=pd.DataFrame({
            "date": ["2024-01-01", "2024-01-03", "2024-01-05"],
            "target_next": [0.01, 0.02, -0.01]
        }),
        expected_strategy="date_index",
        expect_degraded=False
    )
    
    # 场景 6: 模拟真实基金数据差异（40 vs 32）
    print("\n" + "="*60)
    print("测试场景: 真实基金场景 (40 vs 32)")
    print("="*60)
    print("模拟 fund_022771 的数据不匹配问题...")
    
    np.random.seed(42)
    p_test_40 = np.random.uniform(0.3, 0.7, 40)  # 来自 test_select
    test_final_32 = pd.DataFrame({
        "date": pd.date_range("2024-06-01", periods=32, freq='B'),
        "target_next": np.random.randn(32) * 0.02
    })
    test_select_40 = pd.DataFrame({
        "date": pd.date_range("2024-04-01", periods=40, freq='B'),
        "feature": np.random.randn(40)
    })
    
    result = _align_predictions(p_test_40, test_final_32, test_select_40, fund_code="022771")
    
    print(f"✅ 对齐策略: {result.strategy_used}")
    print(f"   是否降级: {result.is_degraded}")
    print(f"   结果长度: {len(result.aligned_predictions)}")
    
    if len(result.aligned_predictions) == 32:
        print("✅ 成功解决维度不匹配问题！")
    else:
        print(f"❌ 长度仍不匹配: 期望 32, 实际 {len(result.aligned_predictions)}")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 所有测试通过！智能降级机制工作正常。")
    else:
        print("❌ 部分测试失败，需要检查。")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
