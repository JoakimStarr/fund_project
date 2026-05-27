#!/usr/bin/env python3
"""
Profile 数据获取深度诊断 - 追踪完整数据流
"""
import sys
import json
import traceback
from datetime import datetime

sys.path.insert(0, '/home/joakim/Project/fund_project/fund_predictor/backend')

def diagnose_profile_data_flow(fund_code: str = "018956", force_refresh: bool = True):
    """诊断 Profile 数据获取的完整流程"""

    print("=" * 100)
    print(f"🔍 Profile 深度诊断报告 - 基金 {fund_code}")
    print(f"⏰ 诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 强制刷新模式: {'开启' if force_refresh else '关闭'}")
    print("=" * 100)

    # ============================================================
    # Step 1: 测试直接调用 classify_fund()
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 1] 直接测试 classify_fund() 函数")
    print("-" * 100)

    try:
        from app.services.fund_profile_service import classify_fund

        print(f"✅ 成功导入 classify_fund 函数")
        print(f"   正在调用 classify_fund('{fund_code}')...")
        print(f"   ⏳ 请稍候，这可能需要几秒钟（网络请求）...")

        profile = classify_fund(fund_code)

        print(f"\n✅ classify_fund() 执行成功！返回结果:")
        print(f"   类型: {type(profile).__name__}")
        print(f"\n   字段详情:")
        for field in ['fund_code', 'fund_name', 'fund_type', 'establish_date',
                     'fund_size', 'manager', 'fee_rate', 'benchmark',
                     'risk_level', 'strategy_text']:
            value = getattr(profile, field, None)
            status = "✅ 有值" if value else "❌ 空值"
            display_value = str(value)[:50] if value else "(空)"
            print(f"     {field:<20}: {display_value:<52} [{status}]")

        # 检查 raw_info
        raw_info = getattr(profile, 'raw_info', {})
        if raw_info:
            print(f"\n   📦 raw_info (原始AKShare数据):")
            print(f"      类型: {type(raw_info).__name__}")
            print(f"      键数量: {len(raw_info)}")
            if raw_info:
                print(f"      内容预览:")
                for key, value in list(raw_info.items())[:10]:
                    display_val = str(value)[:40]
                    print(f"        {key:<25}: {display_val}")
                if len(raw_info) > 10:
                    print(f"        ... 还有 {len(raw_info) - 10} 个字段")
            else:
                print(f"      ⚠️ raw_info 为空字典 {}!")
        else:
            print(f"\n   ❌ raw_info 为 None 或不存在!")

        # 判断结果质量
        has_name = bool(getattr(profile, 'fund_name', ''))
        has_raw = bool(raw_info)

        if has_name and has_raw:
            print(f"\n   🎉 **结论**: 数据获取成功! ✅")
        elif has_raw and not has_name:
            print(f"\n   ⚠️ **结论**: 有原始数据但解析失败 (字段映射问题)")
        elif not has_raw:
            print(f"\n   ❌ **结论**: AKShare 返回了空数据!")
        else:
            print(f"\n   ❓ **结论**: 部分数据缺失")

    except Exception as e:
        print(f"\n❌ classify_fund() 执行失败!")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误信息: {e}")
        print(f"\n   完整堆栈:")
        traceback.print_exc()

    # ============================================================
    # Step 2: 测试 _fetch_from_primary_source()
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 2] 测试主数据源 (_fetch_from_primary_source)")
    print("-" * 100)

    try:
        from app.services.fund_profile_service import _fetch_from_primary_source

        print(f"✅ 成功导入 _fetch_from_primary_source 函数")
        print(f"   正在调用...")

        info = _fetch_from_primary_source(fund_code)

        if info is not None:
            print(f"\n✅ 主数据源 (xueqiu) 返回成功:")
            print(f"   返回类型: {type(info).__name__}")
            print(f"   数据键数: {len(info)}")

            print(f"\n   返回的数据内容:")
            for key, value in list(info.items())[:15]:
                display_val = str(value)[:45]
                is_empty = not value or (isinstance(value, str) and len(value.strip()) == 0)
                status = "⚠️ 空" if is_empty else "✅"
                print(f"     {key:<20}: {display_val:<47} [{status}]")

            if len(info) > 15:
                print(f"     ... 还有 {len(info) - 15} 个字段")
        else:
            print(f"\n❌ 主数据源返回 None!")
            print(f"   这意味着 xueqiu 数据源获取失败")

    except Exception as e:
        print(f"\n❌ _fetch_from_primary_source() 执行异常!")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误信息: {e}")
        print(f"\n   堆栈信息:")
        traceback.print_exc()

    # ============================================================
    # Step 3: 直接测试 AKShare API 调用
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 3] 直接测试 AKShare API (底层调用)")
    print("-" * 100)

    try:
        import akshare as ak

        print(f"✅ AKShare 库已导入")
        print(f"   版本: {ak.__version__}")
        print(f"\n   正在调用 ak.fund_individual_basic_info_xq(symbol='{fund_code}')...")
        print(f"   ⏳ 等待网络响应...")

        info = ak.fund_individual_basic_info_xq(symbol=fund_code)

        print(f"\n✅ AKShare API 调用成功!")
        print(f"   返回类型: {type(info).__name__}")

        if isinstance(info, dict):
            print(f"   字段数量: {len(info)}")
            print(f"\n   所有字段:")
            for key, value in info.items():
                display_val = str(value)[:50]
                is_empty = not value or (isinstance(value, str) and len(value.strip()) == 0)
                status = "⚠️ 空/缺失" if is_empty else "✅ 正常"
                print(f"     {key:<25}: {display_val:<52} [{status}]")
        elif hasattr(info, 'shape'):
            print(f"   DataFrame 形状: {info.shape}")
            print(f"\n   前5行数据:")
            print(info.head().to_string())
        else:
            print(f"   返回值: {info}")

    except Exception as e:
        print(f"\n❌ AKShare API 调用失败!")
        error_type = type(e).__name__
        print(f"   错误类型: {error_type}")
        print(f"   错误信息: {e}")

        # 分析具体原因
        error_str = str(e).lower()

        if 'timeout' in error_str or 'timed out' in error_str:
            print(f"\n   💡 可能原因: 网络超时")
            print(f"   建议: 检查网络连接或使用代理")
        elif '404' in error_str or 'not found' in error_str:
            print(f"\n   💡 可能原因: 基金代码无效或接口URL变更")
            print(f"   建议: 验证基金代码是否正确")
        elif 'connection' in error_str:
            print(f"\n   💡 可能原因: 无法连接到数据源服务器")
            print(f"   建议: 检查DNS/防火墙/代理设置")
        elif 'attribute' in error_str or 'has no attribute' in error_str:
            print(f"\n   💡 可能原因: AKShare 函数名已更改")
            print(f"   建议: 更新 AKShare 到最新版本")
        else:
            print(f"\n   💡 其他错误，请查看详细堆栈:")

        print(f"\n   完整堆栈:")
        traceback.print_exc()

    # ============================================================
    # Step 4: 测试备选数据源 (eastmoney)
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 4] 测试备选数据源 (eastmoney)")
    print("-" * 100)

    try:
        from app.services.fund_profile_service import _normalize_eastmoney_info

        print(f"✅ 导入 eastmoney 相关函数")

        # 尝试直接调用 eastmoney 接口
        print(f"\n   尝试调用东方财富接口...")

        try:
            info_em = ak.fund_individual_basic_info(symbol=fund_code)
            print(f"   ✅ 东方财富接口调用成功!")
            print(f"   返回类型: {type(info_em).__name__}")

            if isinstance(info_em, dict):
                print(f"   字段数量: {len(info_em)}")
                print(f"\n   关键字段:")
                important_fields = ['基金简称', '基金类型', '成立日期', '基金规模', '基金经理']
                for field in important_fields:
                    if field in info_em:
                        val = info_em[field]
                        print(f"     {field}: {val}")
                    else:
                        print(f"     {field}: ❌ 不存在")

                # 测试标准化函数
                normalized = _normalize_eastmoney_info(info_em)
                print(f"\n   标准化后结果:")
                for key in ['fund_code', 'fund_name', 'establish_date', 'fund_size', 'manager']:
                    val = normalized.get(key, 'N/A')
                    print(f"     {key}: {val}")

        except Exception as em_err:
            print(f"   ❌ 东方财富接口调用失败: {em_err}")

    except ImportError:
        print(f"   ⚠️ 未找到 eastmoney 相关函数（可能未实现）")
    except Exception as e:
        print(f"   ❌ 备选数据源测试异常: {e}")

    # ============================================================
    # Step 5: 测试完整的 get_profile() 流程
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 5] 测试完整 get_profile() 流程 (force_refresh={force_refresh})")
    print("-" * 100)

    try:
        from app.services.fund_profile_service import get_profile

        print(f"✅ 导入 get_profile 函数")
        print(f"   正在调用 get_profile('{fund_code}', force_refresh={force_refresh})...")
        print(f"   ⏳ 这将触发完整的: DB查询 → AKShare获取 → 解析 → 缓存 流程")

        profile = get_profile(fund_code, force_refresh=force_refresh)

        print(f"\n✅ get_profile() 执行完成!")

        # 转换为字典显示
        if hasattr(profile, '__dataclass_fields__'):
            from dataclasses import asdict
            profile_dict = asdict(profile)
        else:
            profile_dict = vars(profile)

        print(f"\n   最终返回的 Profile 对象:")
        for key, value in profile_dict.items():
            if key == 'raw_info' and isinstance(value, dict):
                print(f"     {key:<20}: <dict with {len(value)} keys>")
            elif key == 'strategy_keywords':
                print(f"     {key:<20}: {value}")
            else:
                display_val = str(value)[:50] if value else '(空)'
                has_value = bool(value) and str(value).strip()
                status = "✅" if has_value else "❌"
                print(f"     {key:<20}: {display_val:<52} [{status}]")

        # 检查 stale 标记
        if hasattr(profile, 'stale') and profile.stale:
            print(f"\n   ⚠️ 注意: 此 Profile 标记为 stale=True (使用了过期缓存)")

    except Exception as e:
        print(f"\n❌ get_profile() 执行失败!")
        print(f"   错误: {e}")
        traceback.print_exc()

    # ============================================================
    # Step 6: 检查数据库中的实际存储
    # ============================================================
    print("\n\n" + "📊" + " " * 98)
    print(f"[Step 6] 检查数据库实际存储内容")
    print("-" * 100)

    try:
        import sqlite3

        db_path = '/home/joakim/Project/fund_project/fund_predictor/output/app.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询该基金的记录
        cursor.execute("SELECT * FROM fund_profiles WHERE fund_code=?", [fund_code])
        row = cursor.fetchone()

        if row:
            columns = [desc[0] for desc in cursor.description]

            print(f"✅ 在数据库中找到 {fund_code} 的记录:")
            print(f"   记录数: 1 条\n")

            for i, col in enumerate(columns):
                value = row[i]
                if col == 'raw_info_json' and value:
                    try:
                        parsed = json.loads(value)
                        print(f"   {col:<20}: <JSON with {len(parsed)} keys>")
                    except:
                        print(f"   {col:<20}: {str(value)[:60]}...")
                else:
                    display_val = str(value)[:55] if value else '(NULL/空)'
                    has_value = bool(value) and str(value).strip() and value != '' and value != '{}'
                    status = "✅" if has_value else "❌"
                    print(f"   {col:<20}: {display_val:<57} [{status}]")

            # 特别检查 fetched_at 和 TTL
            fetched_at = row[columns.index('fetched_at')]
            cache_ttl = row[columns.index('cache_ttl_days')]
            print(f"\n   ⏰ 缓存时间分析:")
            print(f"      获取时间: {fetched_at}")
            print(f"      TTL(天): {cache_ttl}")

            if fetched_at:
                from datetime import datetime as dt
                try:
                    fetch_dt = dt.fromisoformat(fetched_at.replace('Z', '+00:00'))
                    age_hours = (dt.now(fetch_dt.tzinfo) - fetch_dt).total_seconds() / 3600
                    print(f"      已缓存: {age_hours:.1f} 小时 ({age_hours/24:.2f} 天)")
                    if age_hours / 24 > cache_ttl:
                        print(f"      状态: ⚠️ 已过期! 应该重新获取")
                    else:
                        print(f"      状态: ✅ 未过期")
                except:
                    pass

        else:
            print(f"❌ 数据库中未找到 {fund_code} 的记录!")
            print(f"   这意味着从未成功获取过该基金的数据")

        conn.close()

    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        traceback.print_exc()

    # ============================================================
    # 总结
    # ============================================================
    print("\n\n" + "=" * 100)
    print("🏁 诊断完成 - 总结与建议")
    print("=" * 100)


if __name__ == "__main__":
    fund_code = sys.argv[1] if len(sys.argv) > 1 else "018956"
    force_refresh = '--no-refresh' not in sys.argv

    diagnose_profile_data_flow(fund_code, force_refresh)
