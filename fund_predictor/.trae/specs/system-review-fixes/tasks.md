# Tasks

## Phase 1: 严重缺陷修复（P0）

- [ ] Task 1: 修复冷启动盲区 — cold_start.py 阈值与 MIN_TRAIN_ROWS 对齐
  - [ ] 1.1 将 `MIN_DAYS_FOR_COLD_START` 从 120 改为 220（对齐 MIN_TRAIN_ROWS）
  - [ ] 1.2 修改 `should_use_group_model()` 返回逻辑：220-400天仍返回 True 但带 blend_weight
  - [ ] 1.3 修改 `get_group_model_prediction()` blend_weight 计算：≥220天开始衰减，400天完全切换
  - [ ] 1.4 更新 config.yaml `cold_start.group_model_days` 为 250
  - [ ] 1.5 添加测试：150天历史基金应走群体模型不报错

- [ ] Task 2: WF-CV 动态参数适配
  - [ ] 2.1 在 model_selection_service.py 入口处计算实际数据量 T
  - [ ] 2.2 动态设 train_window = min(500, T*0.55), valid_window = min(60, T*0.22)
  - [ ] 2.3 计算最大可运行轮数，<3 轮时降级为 Hold-out（后20%验证）
  - [ ] 2.4 在 metrics.json 中记录 actual_wf_rounds 和 validation_method 字段
  - [ ] 2.5 添加测试：300行数据应降级为 Hold-out 不崩溃

- [ ] Task 3: 保形预测校准集隔离
  - [ ] 3.1 在 model_selection_service 四段划分后显式命名 X_calib = test_select 段
  - [ ] 3.2 prediction_service 调用 conformal_interval 时明确传入 X_calib
  - [ ] 3.3 conformal.py docstring 和日志中标注校准集来源
  - [ ] 3.4 添加测试：确认校准集不与 train/valid 重叠

- [ ] Task 4: Benchmark 权重智能解析
  - [ ] 4.1 在 fund_profile_service.py 新增 `_parse_benchmark_weight(benchmark_str)` 函数
  - [ ] 4.2 用正则提取 "××%" 格式的权重数值
  - [ ] 4.3 Level 1 分类增加权重判断: >0.65→equity, 0.40-0.65→balanced, <0.40→bond
  - [ ] 4.4 无法解析数值时回退 Level 2 名称推断
  - [ ] 4.5 添加测试："沪深300×80%+中债×20%" → hybrid_equity

- [ ] Task 5: 数据新鲜度检查 + 缓存线程安全
  - [ ] 5.1 data_service.py 中记录每只基金的 last_update_time (CSV mtime)
  - [ ] 5.2 prediction_service 预测前检查数据时效，超期附加 data_warning
  - [ ] 5.3 config.yaml 新增 `data.stale_warning_days: 3`
  - [ ] 5.4 _NAV_CACHE 改用 threading.Lock 保护并发读写
  - [ ] 5.5 添加测试：并发读取缓存无竞态条件

- [ ] Task 6: 货币基金强制 skip_prediction 统一
  - [ ] 6.1 classify_fund() 末尾强制约束: IF fund_type=="money_market" THEN skip=True
  - [ ] 6.2 routing_service 移除冗余的 fund_type=="money_market" 分支
  - [ ] 6.3 统一走 skip_prediction == True 判断入口
  - [ ] 6.4 添加测试：货币基金无论分类路径如何都返回 skip 响应

## Phase 2: 中等问题修复（P1）

- [ ] Task 7: IC 计算改用 Spearman RankIC
  - [ ] 7.1 factor_screening.py Round 1: pearsonr → spearmanr
  - [ ] 7.2 ic_threshold 从 0.02 调整至 0.03
  - [ ] 7.3 ICIR 基于 Spearman IC 序列重新计算
  - [ ] 7.4 保留 Pearson IC 作为参考信息记录到 ic_report
  - [ ] 7.5 添加测试：Spearman IC 筛选结果合理性

- [ ] Task 8: 模型选择加入方向准确率
  - [ ] 8.1 walk_forward_cv 每轮额外记录 direction_accuracy (pred方向 vs 实际方向)
  - [ ] 8.2 模型选择引入联合得分: score = 0.6*mae_rank + 0.4*(1-dir_acc_rank)
  - [ ] 8.3 设定最低方向准确率门槛 (>52%) 排除无效候选
  - [ ] 8.4 metrics.json 新增 direction_accuracy 和 selection_score 字段
  - [ ] 8.5 添加测试：纯 MAE 最优但方向准确率50%的模型不应被选中

- [ ] Task 9: VIF 改为相关性聚类去重
  - [ ] 9.1 新增 _cluster_dedup_features() 函数
  - [ ] 9.2 计算特征间 Spearman 相关系数矩阵
  - [ ] 9.3 |corr|>0.80 归簇，每簇保留 |IC| 最大者
  - [ ] 9.4 替换原 VIF 逐步剔除逻辑（保留作为 fallback）
  - [ ] 9.5 添加测试：高相关特征组只保留IC最大的

- [ ] Task 10: index_equity 规则引擎补全
  - [ ] 10.1 routing_service 对 index_equity 类型直接走规则路径
  - [ ] 10.2 规则公式: pred_return = index_ret * (1 - daily_fee_rate)
  - [ ] 10.3 区间: 历史 tracking error ±2σ (固定区间)
  - [ ] 10.4 index_rule_engine.py 补全完整规则实现
  - [ ] 10.5 添加测试：指数基金预测结果接近标的指数收益率

- [ ] Task 11: 四段划分与 WF-CV 边界厘清
  - [ ] 11.1 明确变量命名: X_train, X_valid, X_calib(=test_sel), X_final(=test_fin)
  - [ ] 11.2 WF-CV 仅在 X_train+X_valid 上运行
  - [ ] 11.3 X_final 严格隔离，仅用于最终报告
  - [ ] 11.4 代码注释和文档标注数据流边界
  - [ ] 11.5 添加测试：X_final 数据未参与任何训练/校准步骤

- [ ] Task 12: 残差修正数据来源明确化
  - [ ] 12.1 定义 prediction_history 表结构（如不存在则在 db/models.py 添加）
  - [ ] 12.2 residual_adaptive_correction 显式从 DB 读取 recent_errors
  - [ ] 12.3 边界处理: 历史 <5 条时跳过修正(bias=0)，metrics.json 记录状态
  - [ ] 12.4 首次部署空表时优雅降级不报错
  - [ ] 12.5 添加测试：空历史记录时不崩溃

## Phase 3: 架构优化（P2）

- [ ] Task 13: _NAV_CACHE 线程安全加固（Task 5.4 已覆盖部分）
  - [ ] 13.1 确认 Lock 保护覆盖所有读写路径
  - [ ] 13.2 添加缓存命中/未命中计数指标（可选 perf 日志）

## Task Dependencies
- [Task 2] depends on [Task 1] (WF-CV 依赖冷启动阈值对齐后的数据量判断)
- [Task 3] depends on [Task 2] (校准集依赖四段划分完成)
- [Task 7-12] 无依赖，可与 Phase 1 并行
- [Task 13] depends on [Task 5]
