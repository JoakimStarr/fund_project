# 系统审查缺陷修复 Spec

## Why

基于 `docs/system_review_and_improvements.md` 的深度代码审查，发现 **6 个严重缺陷**（导致崩溃/错误预测）和 **6 个中等问题**（影响精度/稳定性）。本 Spec 覆盖全部严重缺陷和关键中等问题，按优先级分批修复。

## What Changes

### 严重缺陷（P0，必须修复）
1. **冷启动盲区 120–220 天**：`cold_start.py` 与 `MIN_TRAIN_ROWS=220` 不对齐，导致该区间基金两边都不管
2. **WF-CV 参数失配**：固定 24 月训练窗口在数据不足 3 年时几乎无法运行
3. **保形预测校准集来源不明**：可能复用 Valid 集导致数据泄露、区间偏窄
4. **Benchmark 映射错误**：80% 权重股票基准被误判为 `hybrid_balanced`
5. **缓存无更新机制**：CSV 永不刷新，无调度无告警
6. **货币基金双重判断漏判**：`skip_prediction` 与 `fund_type` 不一致时绕过跳过逻辑

### 中等问题（P1，影响质量）
7. **IC 用 Pearson 非 Spearman**：对厚尾分布敏感，应改用 RankIC
8. **模型选择只看 MAE**：忽略方向准确率，可能选到"永远预测0"的模型
9. **VIF 逐步剔除路径依赖**：结果不可复现，改为聚类去重
10. **index_equity 规则引擎未完成**：指数基金走 ML 浪费资源且精度差
11. **四段划分与 WF-CV 边界未厘清**：Test_final 可能泄露
12. **残差修正数据来源缺失文档**：`recent_errors` 来源不明

### 架构优化（P2）
13. **_NAV_CACHE 线程安全**：全局 dict 无锁保护
14. **货币基金强制 skip**：统一判断入口

## Impact

- Affected specs: prediction-model-audit（审计发现的问题落地修复）
- Affected code:
  - `backend/app/services/cold_start.py` — 重写阈值对齐逻辑
  - `backend/app/services/model_selection_service.py` — 动态 WF-CV 参数 + 方向准确率联合选模
  - `backend/app/services/prediction_service.py` — 校准集明确为 Test_select 段
  - `backend/app/services/fund_profile_service.py` — Benchmark 解析权重 + 货币基金强制 skip
  - `backend/app/services/routing_service.py` — 统一 skip 入口
  - `backend/app/services/features/factor_screening.py` — IC 改 Spearman + VIF 改聚类去重
  - `backend/app/services/data_service.py` — 缓存线程安全 + 数据新鲜度检查
  - `backend/app/services/postprocessing/conformal.py` — 明确校准集来源
  - `backend/app/rules/index_rule_engine.py` — 补全指数规则引擎

## ADDED Requirements

### Requirement: 冷启动阈值对齐 MIN_TRAIN_ROWS

系统 SHALL 在 `cold_start.py` 中将群体模型使用范围延伸至数据满足 `MIN_TRAIN_ROWS(220)` 之后：

- 0–219 天：使用群体模型（blend_weight 固定 1.0，不触发个体训练）
- ≥220 天：开始 blend_weight 从 1.0 线性衰减至 0（400 天完全切换）

#### Scenario: 150 天历史的基金发起预测
- **WHEN** 基金历史 150 天 (<220 且 >120)
- **THEN** 使用群体模型返回预测，不抛 InsufficientDataError

#### Scenario: 250 天历史的基金发起预测
- **WHEN** 基金历史 250 天 (≥220)
- **THEN** blend_weight = (250-220)/(400-220) = 0.167，群体占 91.7% + 微调

### Requirement: WF-CV 动态参数适配

系统 SHALL 根据实际数据量 T 动态计算 Walk-Forward CV 参数：

- `train_window = min(500, int(T * 0.55))`
- `valid_window = min(60, int(T * 0.22))`
- 若可运行轮数 < 3，降级为 Hold-out 验证（后 20% 为验证集）
- metrics.json 中记录实际轮数和验证方法

#### Scenario: 数据量 300 行的基金训练
- **WHEN** 总数据 300 行
- **THEN** train_window=165, valid_window=66, 可运行约 1-2 轮 → 降级为 Hold-out

### Requirement: 保形预测校准集隔离

系统 SHALL 明确使用 Test_select（13% 段）作为保形预测校准集，该段不得用于任何训练步骤：

- model_selection_service 中四段划分后显式命名 X_calib = test_select 段
- conformal_interval() 的 docstring 和日志中标注校准集来源
- prediction_service 中传参时明确传入 X_calib

#### Scenario: 正常四段划分后的校准
- **WHEN** 四段划分为 train/valid/test_sel/test_fin
- **THEN** conformal_interval 使用 test_sel 作为校准集，非 valid 集

### Requirement: Benchmark 权智能解析

系统 SHALL 解析基准字符串中的数值权重以正确分类：

- 提取 "沪深300×80%" → equity_weight = 0.80 → hybrid_equity
- 提取 "50%+50%" → equity_weight = 0.50 → hybrid_balanced
- 规则: equity_weight > 0.65 → hybrid_equity; 0.40–0.65 → balanced; < 0.40 → bond
- 无法解析数值时回退 Level 2 名称推断

#### Scenario: "沪深300×80%+中证全债×20%"
- **WHEN** benchmark 含 "80%"
- **THEN** 分类为 hybrid_equity（非 hybrid_balanced）

### Requirement: 数据新鲜度检查

系统 SHALL 在预测接口中检查数据时效：

- data_service 中记录每只基金的 last_update_time（从 CSV mtime 获取）
- 预测时若数据距今 > 3 个交易日，响应附加 `data_warning` 字段
- config.yaml 新增 `data.stale_warning_days: 3`

#### Scenario: 数据 5 天未更新
- **WHEN** fund_nav CSV 最后修改时间距今 > 3 天
- **THEN** 预测响应含 `{ "data_warning": "数据已滞后 N 天" }`

### Requirement: 货币基金强制 skip_prediction

系统 SHALL 在 classify_fund 中保证一致性约束：

```
IF fund_type == "money_market": THEN skip_prediction = True（无条件强制）
```

routing_service 移除冗余的 money_market 分支，统一走 skip_prediction 判断。

#### Scenario: 仅命中 Level 2 名称关键词的货币基金
- **WHEN** fund_type="money_market" 但 skip_prediction 未被设为 True
- **THEN** classify_fund 强制设置 skip_prediction=True

## MODIFIED Requirements

### Requirement: 因子筛选 IC 计算

因子预筛选 Round 1 的 IC 计算底层函数 SHALL 从 `pearsonr` 改为 `spearmanr`：

- ic_threshold 同步调整至 0.03（Spearman IC 通常略低）
- ICIR 基于 Spearman IC 序列计算
- 保留 Pearson IC 作为参考信息记录但不参与筛选决策

### Requirement: 模型选择标准

WF-CV 模型选择 SHALL 引入方向准确率联合指标：

- 每轮验证同时记录 direction_accuracy
- 联合得分: `score = 0.6 * norm_mae_rank + 0.4 * (1 - dir_acc_rank)`
- 或设定最低方向准确率门槛 (>52%) 排除无效候选
- metrics.json 新增 direction_accuracy 字段

### Requirement: VIF 共线性消除

VIF 筛选 SHALL 从逐步剔除改为相关性聚类去重：

1. 计算特征间 Spearman 相关系数矩阵
2. |corr| > 0.80 的归为一个簇
3. 每簇保留 |IC| 最大的特征
4. 结果确定性（由 IC 大小决定）

### Requirement: index_equity 规则引擎

路由层对 index_equity 类型 SHALL 完全绕过 ML 流程：

- 点预测: pred = index_return * (1 - daily_fee_rate)
- 区间: 历史 tracking error ±2σ
- 路由直接返回规则结果，不调用 prediction_service.predict_next()

## REMOVED Requirements

无（纯增量修复，不删除已有功能）
