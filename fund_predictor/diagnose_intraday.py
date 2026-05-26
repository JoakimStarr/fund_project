#!/usr/bin/env python3
"""
Intraday 估算诊断脚本 - 调查为什么涨跌幅为 0%
"""
import sys
import json
from datetime import datetime

sys.path.insert(0, '/home/joakim/Project/fund_project/fund_predictor/backend')

def diagnose_intraday_zero_return(fund_code: str = "018956"):
    """诊断 Intraday 估算返回 0% 的原因"""

    print("=" * 80)
    print(f"🔍 Intraday 诊断报告 - 基金 {fund_code}")
    print(f"⏰ 诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Step 1: 检查基金净值数据
    print("\n📊 [Step 1] 检查基金净值数据")
    print("-" * 80)
    try:
        from app.services.data_service import get_fund_nav
        fund_df, fund_meta = get_fund_nav(fund_code, require_fresh=False)

        if fund_df.empty:
            print("❌ 基金净值数据为空！")
            return

        print(f"✅ 基金净值数据获取成功")
        print(f"   数据行数: {len(fund_df)}")
        print(f"   最新日期: {fund_df.iloc[-1]['date']}")
        print(f"   最新净值: {fund_df.iloc[-1]['nav']:.4f}")
        print(f"   数据来源: {fund_meta.get('source_used', '未知')}")

        # 显示最近5条
        print("\n   最近5条记录:")
        print(f"   {'日期':<12} {'净值':>10} {'累计净值':>12}")
        print("   " + "-" * 40)
        recent = fund_df.tail(5)
        for i, (_, row) in enumerate(recent.iterrows()):
            acc_nav = row.get('acc_nav', row['nav'])
            nav = row['nav']
            date = row['date']
            print(f"   {str(date):<12} {float(nav):>10.4f} {float(acc_nav):>12.4f}")

    except Exception as e:
        print(f"❌ 获取基金净值失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: 检查路径A（持仓映射）
    print("\n\n📈 [Step 2] 检查路径A - 持仓映射法")
    print("-" * 80)
    try:
        from app.services.intraday_service import _get_path_a_return
        path_a_ret, path_a_meta = _get_path_a_return(fund_code)

        print(f"路径A 返回值: {path_a_ret:.6f} ({path_a_ret*100:.4f}%)")
        print(f"可用状态: {path_a_meta.get('available', False)}")

        if path_a_meta.get('available'):
            print(f"\n✅ 路径A 可用:")
            print(f"   Proxy R²: {path_a_meta.get('proxy_r2', 'N/A')}")
            print(f"   可用持仓数: {path_a_meta.get('available_count', 0)}")
            print(f"   Proxy状态: {path_a_meta.get('proxy_status', 'N/A')}")
        else:
            print(f"\n⚠️ 路径A 不可用:")
            if 'error' in path_a_meta:
                print(f"   错误: {path_a_meta['error']}")

    except Exception as e:
        print(f"❌ 路径A 执行异常: {e}")
        import traceback
        traceback.print_exc()
        path_a_ret = 0.0

    # Step 3: 检查路径B（指数回归）
    print("\n\n📉 [Step 3] 检查路径B - 指数回归法")
    print("-" * 80)
    try:
        from app.services.intraday_service import _get_path_b_return
        path_b_ret, path_b_meta = _get_path_b_return(fund_code)

        print(f"路径B 返回值: {path_b_ret:.6f} ({path_b_ret*100:.4f}%)")
        print(f"可用状态: {path_b_meta.get('available', False)}")

        if path_b_meta.get('available'):
            print(f"\n✅ 路径B 可用:")
            print(f"   回归指数: {path_b_meta.get('regression_index', 'N/A')}")
            print(f"   Beta系数: {path_b_meta.get('beta', 'N/A')}")
            print(f"   R²得分: {path_b_meta.get('r2', 'N/A')}")
            print(f"   回归窗口: {path_b_meta.get('window', 'N/A')} 天")
            print(f"   指数最新收益: {path_b_meta.get('latest_index_ret', 'N/A')}")

            # 关键检查：指数最新收益率是否为0？
            latest_idx_ret = path_b_meta.get('latest_index_ret')
            if latest_idx_ret is not None and abs(latest_idx_ret) < 0.0001:
                print(f"\n🚨 **关键发现**: 指数最新收益率 ≈ 0！")
                print(f"   这意味着:")
                print(f"   1. 可能是非交易时间（周末/节假日/休市）")
                print(f"   2. 指数数据未更新（仍显示昨日收盘）")
                print(f"   3. 数据源缺少实时数据")
        else:
            print(f"\n⚠️ 路径B 不可用:")
            if 'error' in path_b_meta:
                print(f"   错误: {path_b_meta['error']}")

    except Exception as e:
        print(f"❌ 路径B 执行异常: {e}")
        import traceback
        traceback.print_exc()
        path_b_ret = 0.0

    # Step 4: 检查融合权重和最终结果
    print("\n\n⚖️ [Step 4] 检查融合计算")
    print("-" * 80)
    try:
        from app.services.intraday_service import _compute_fusion_weight
        w_a, w_b = _compute_fusion_weight(fund_code)

        fused_ret = w_a * path_a_ret + w_b * path_b_ret

        print(f"融合权重: 路径A={w_a:.4f}, 路径B={w_b:.4f}")
        print(f"融合结果: {fused_ret:.6f} ({fused_ret*100:.4f}%)")
        print(f"\n分解:")
        print(f"  路径A贡献: {w_a * path_a_ret:.6f} ({w_a * path_a_ret * 100:.4f}%)")
        print(f"  路径B贡献: {w_b * path_b_ret:.6f} ({w_b * path_b_ret * 100:.4f}%)")

        last_nav = float(fund_df.iloc[-1]['nav'])
        estimated_nav = last_nav * (1 + fused_ret)
        print(f"\n最终结果:")
        print(f"  上次净值: {last_nav:.4f}")
        print(f"  估算净值: {estimated_nav:.4f}")
        print(f"  估算涨跌: {fused_ret * 100:.4f}%")

        if abs(fused_ret) < 0.0001:
            print(f"\n🚨 **确认问题**: 融合结果接近 0！")
            print(f"\n根因分析:")
            if abs(path_a_ret) < 0.0001 and abs(path_b_ret) < 0.0001:
                print(f"  ❌ 两个路径都返回 ~0")
                print(f"     → 可能原因: 非交易时间 + 无实时数据")
            elif abs(path_a_ret) < 0.0001:
                print(f"  ❌ 主要原因是路径A返回 0 (权重={w_a})")
            elif abs(path_b_ret) < 0.0001:
                print(f"  ❌ 主要原因是路径B返回 0 (权重={w_b})")

    except Exception as e:
        print(f"❌ 融合计算异常: {e}")
        import traceback
        traceback.print_exc()

    # Step 5: 检查市场数据状态
    print("\n\n📊 [Step 5] 检查市场数据状态")
    print("-" * 80)
    try:
        from app.services.data_service import load_market_data
        indexes, index_meta = load_market_data(require_fresh=False)

        print(f"可用的指数: {list(indexes.keys())}")

        for name, idx_df in indexes.items():
            if not idx_df.empty:
                last_date = idx_df.iloc[-1]['date']
                last_close = idx_df.iloc[-1]['close']
                print(f"\n{name}:")
                print(f"   最后日期: {last_date}")
                print(f"   最后收盘: {last_close:.2f}")

                # 计算最近的变化
                if len(idx_df) >= 2:
                    prev_close = idx_df.iloc[-2]['close']
                    change_pct = (last_close - prev_close) / prev_close * 100
                    print(f"   前一日收盘: {prev_close:.2f}")
                    print(f"   变化率: {change_pct:.4f}%")

                    if abs(change_pct) < 0.001:
                        print(f"   ⚠️ 变化率接近 0 (可能非交易时间)")

    except Exception as e:
        print(f"❌ 获取市场数据失败: {e}")

    # Step 6: 时间检查
    print("\n\n⏰ [Step 6] 当前时间与交易时间判断")
    print("-" * 80)
    now = datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"星期: {now.strftime('%A')}")

    # 判断是否为交易日（简化版）
    weekday = now.weekday()  # 0=周一, 6=周日
    hour = now.hour
    minute = now.minute

    is_weekend = weekday >= 5
    is_trading_time = (9 <= hour < 15) or (hour == 9 and minute >= 30)

    print(f"是否周末: {'是 ⚠️' if is_weekend else '否 ✅'}")
    print(f"是否交易时间段 (9:30-15:00): {'是 ✅' if is_trading_time else '否 ⚠️'}")

    if is_weekend or not is_trading_time:
        print(f"\n🎯 **根本原因确认**: 当前为非交易时间！")
        print(f"   这就是为什么指数涨跌幅为 0 → 导致估算涨跌幅为 0")
        print(f"\n💡 解决方案:")
        print(f"   1. 在交易时间（工作日 9:30-15:00）测试")
        print(f"   2. 或者使用历史回测功能验证逻辑正确性")
        print(f"   3. 或者模拟实时数据测试")
    else:
        print(f"\n✅ 当前应该是交易时间，如果仍返回0，请检查数据源")

    print("\n" + "=" * 80)
    print("🏁 诊断完成")
    print("=" * 80)


if __name__ == "__main__":
    fund_code = sys.argv[1] if len(sys.argv) > 1 else "018956"
    diagnose_intraday_zero_return(fund_code)
