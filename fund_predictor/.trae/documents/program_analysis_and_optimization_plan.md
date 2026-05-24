# 基金净值预测系统 —— 策略方案驱动的全面改进计划

> 基于 `fund_nav_prediction_strategy.md` v1.0 策略文档

---

## 零、现有系统与策略方案的差距分析

| 策略要求 | 现有实现 | 差距 |
|---------|---------|------|
| 基金分类路由（偏股/债券/指数/灵活/FOF/QDII） | 无分类，所有基金统一处理 | **缺失** |
| T日盘中净值估算 | 无 | **缺失** |
| 债券物理先验（-久期×Δy） | 无 | **缺失** |
| 指数基金规则优先 | 无，同ML流程 | **缺失** |
| 灵活配置两阶段仓位估算 | 无 | **缺失** |
| 因子体系按类型分化 | 通用特征（60-80维） | **不足** |
| 样本时间权重（指数衰减） | 无 | **缺失** |
| 因子预筛选（IC/VIF） | 无 | **缺失** |
| Walk-Forward 时序交叉验证 | 固定 65/17/18 划分 | **不足** |
| 模型集成（LightGBM+LSTM+Transformer+Stacking） | 单一模型，无集成 | **不足** |
| Conformal Prediction 置信区间 | 残差分位数 | **不足** |
| 预测值约束规则 | 无 | **缺失** |
| 特殊时期置信度调整 | 部分（暴露漂移检测） | **部分** |
| 日频滚动更新 + 月频全量重训 | 手动触发重训 | **缺失** |
| 冷启动策略（新基金） | 无（要求 MIN_TRAIN_ROWS=220） | **缺失** |
| 多步预测（3日/5日） | 仅 T+1 | **缺失** |
| 群体模型 + 个体残差修正 | 仅个体模型 | **不足** |
| 持仓数据时效性管理 | 仅用最新持仓 | **不足** |
| 沪深300/IC/IR评估体系 | 基础RMSE/MAE/AUC | **不足** |
| 每日数据更新流程 | start.sh 简单启动 | **不足** |
| 宏观因子（利率/CPI/PMI） | 无 | **缺失** |
| 资金流向/情绪因子 | 无 | **缺失** |
| 日历效应因子 | 无 | **缺失** |

---

## 一、架构总览（目标状态）

```
                        ┌──────────────────────────────┐
                        │      API 网关 (FastAPI)        │
                        │   /api/v1/predict/estimate    │ ← T日盘中估算
                        │   /api/v1/predict/tomorrow    │ ← T+1 预测
                        │   /api/v1/predict/multi-step  │ ← 多步预测
                        │   /api/v1/train               │ ← 异步训练
                        │   /api/v1/fund/(code)/profile │ ← 基金画像
                        └──────────────┬───────────────┘
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
        ┌───────▼───────┐    ┌────────▼────────┐    ┌────────▼────────┐
        │  基金画像解析  │    │   分类路由引擎    │    │   任务队列       │
        │  - 类型分类    │───▶│  - 偏股路由       │───▶│  (Celery/ARQ)    │
        │  - 策略提取    │    │  - 债券路由       │    │  - 异步训练      │
        │  - 规模评估    │    │  - 指数路由       │    │  - 日频更新      │
        └───────────────┘    │  - 灵活路由       │    │  - 月频重训      │
                             │  - FOF递归        │    └─────────────────┘
                             │  - QDII路由       │
                             └────────┬──────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼───────┐   ┌────────▼────────┐   ┌────────────────────────▼──┐
│ 偏股模型流水线 │   │ 债券模型流水线   │   │ 指数/ETF规则引擎          │
│ - 基准暴露因子 │   │ - 物理先验特征   │   │ - 标的指数涨跌映射         │
│ - 重仓股映射   │   │ - 利率曲线因子   │   │ - 跟踪误差ML校正           │
│ - 技术/动量    │   │ - 信用利差因子   │   │ - ETF折溢价/申赎           │
│ - 风格因子     │   │ - 流动性因子     │   └──────────────────────────┘
│ - 情绪/另类    │   │ - 宏观政策因子   │
│ - 日历效应     │   │ - 可转债专项     │
│ - 宏观因子     │   └─────────────────┘
│ - 资金流向     │
└───────┬───────┘
        │
┌───────▼───────────────────────────────┐
│          集成学习层                     │
│  Layer1: LightGBM + LSTM + Transformer │
│  Layer2: Stacking (Ridge)              │
│  Layer3: 残差自适应修正                 │
└───────┬───────────────────────────────┘
        │
┌───────▼───────────────┐
│  后处理层              │
│  - Conformal Prediction│
│  - 类型约束规则        │
│  - 特殊时期置信度调整   │
└───────────────────────┘
```

---

## 二、分阶段实施计划

### 阶段 0：修复 P0 致命问题（立即执行）

这些问题直接影响现有系统的正确性，必须在任何新功能之前修复。

#### 0.1 修复指数数据 require_fresh 不生效

**文件**: `backend/app/services/data_service.py:234`

```python
# 修改前
if cached is not None and not _is_stale(cached):

# 修改后
if cached is not None and not require_fresh and not _is_stale(cached):
```

#### 0.2 修复训练/测试集双重使用

**文件**: `backend/app/services/model_selection_service.py`

修改 `_split_train_valid_test` 为四段划分：train(55%) / valid(22%) / test_select(13%) / test_final(10%)

- `train + valid` 用于粗筛和 walk-forward 精排
- `test_select`（新）用于 final_metrics 选最佳模型
- `test_final`（新）仅用于最终回测报告，不参与任何选模

#### 0.3 修复模型监控文件路径

**文件**: `backend/app/services/model_selection_service.py:813` 和 `prediction_service.py:475`

```python
# 修改前
monitor_path = Path("models") / fund_code / "t_plus_1_close" / "model_monitoring.json"

# 修改后
from app.core.config import MODEL_DIR
monitor_path = MODEL_DIR / fund_code / "t_plus_1_close" / "model_monitoring.json"
```

---

### 阶段 1：基金画像与分类路由（核心基础）

这是策略方案中最核心的基础设施——不同基金类型必须走不同的预测流水线。

#### 1.1 基金画像解析服务 (新文件)

**新建**: `backend/app/services/fund_profile_service.py`

功能：
- 调用 `ak.fund_individual_basic_info_xq` 获取基金基本信息
- 解析三级分类：`基金类型`（主要）→ `业绩比较基准`（辅助）→ `投资策略`（兜底）
- 输出标准化分类标签：
  ```
  hybrid_equity, equity_active, hybrid_balanced, hybrid_bond,
  hybrid_flexible, bond_pure, bond_mixed, bond_convertible,
  index_equity, index_bond, fof, qdii, money_market(直接跳过)
  ```
- 提取：规模、基金经理、策略关键词、业绩基准

**分类判定逻辑**:

```python
def classify_fund(fund_code: str) -> FundProfile:
    info = ak.fund_individual_basic_info_xq(fund_code)
    fund_type = info.get("基金类型", "")
    
    if "货币" in fund_type:
        return FundProfile(type="money_market", skip=True)
    if "指数" in fund_type or "ETF" in fund_type:
        return FundProfile(type="index_equity")
    if "债券" in fund_type:
        if "可转债" in fund_type: return FundProfile(type="bond_convertible")
        if "纯债" in fund_type: return FundProfile(type="bond_pure")
        return FundProfile(type="bond_mixed")
    if "混合" in fund_type:
        if "偏股" in fund_type: return FundProfile(type="hybrid_equity")
        if "偏债" in fund_type: return FundProfile(type="hybrid_bond")
        if "平衡" in fund_type: return FundProfile(type="hybrid_balanced")
        if "灵活" in fund_type: return FundProfile(type="hybrid_flexible")
    if "股票" in fund_type: return FundProfile(type="equity_active")
    if "FOF" in fund_type or "基金中基金" in fund_type: return FundProfile(type="fof")
    if "QDII" in fund_type: return FundProfile(type="qdii")
    
    # 业绩比较基准辅助判定
    benchmark = info.get("业绩比较基准", "")
    if "沪深300" in benchmark: return FundProfile(type="hybrid_equity")
    if "中债" in benchmark: return FundProfile(type="bond_pure")
    
    return FundProfile(type="hybrid_equity")  # 默认偏股
```

#### 1.2 分类路由引擎 (新文件)

**新建**: `backend/app/services/routing_service.py`

```python
ROUTING_TABLE = {
    "hybrid_equity": EquityPipeline,
    "equity_active": EquityPipeline,
    "hybrid_balanced": BalancedPipeline,
    "hybrid_bond": BondBiasedPipeline,
    "hybrid_flexible": FlexiblePipeline,
    "bond_pure": BondPipeline,
    "bond_mixed": BondPipeline,
    "bond_convertible": ConvertibleBondPipeline,
    "index_equity": IndexRulePipeline,
    "index_bond": IndexBondPipeline,
    "fof": FofRecursivePipeline,
    "qdii": QdiiPipeline,
    "money_market": SkipPipeline,
}
```

#### 1.3 修改入口整合基金画像

**修改**: `backend/app/api/fund.py` 的 predict 接口

- 先调用 `fund_profile_service.classify_fund()` 获取分类
- 货币基金直接返回 "净值恒为1，无需预测"
- 其他类型按路由表分发到对应的预测流水线
- 预测结果中包含 `fund_profile` 字段

---

### 阶段 2：因子体系按类型分化

#### 2.1 偏股类因子增强 (修改现有 feature_service.py + 新增文件)

**新建**: `backend/app/services/features/equity_features.py`

在现有因子基础上新增：

| 类别 | 新增因子 | 数据来源 |
|------|---------|---------|
| 宏观 | 10年期国债收益率、CPI、PMI | akshare 宏观模块 |
| 资金流向 | 北向资金净流入、融资余额变化 | akshare |
| 情绪 | 涨跌比、新高新低比、恐慌指数代理 | 指数行情计算 |
| 日历 | 星期几哑变量、月末/季末效应、节前效应 | 日期衍生 |
| 基金特质 | 规模变化率、同类排名 | akshare 基金信息 |

**因子预筛选** (新增):

```python
def pre_screen_factors(X, y, threshold_ic=0.02, threshold_vif=10):
    # 1. IC 检验：PEARSON/SPEARMAN 相关系数绝对值 < 0.02 的因子排除
    # 2. VIF 检验：VIF > 10 的因子剔除
    # 3. ICIR 检验：IC均值/IC标准差 < 0.5 的因子排除
    # 4. 衰减测试：因子的预测有效期
    return screened_features, screening_report
```

#### 2.2 债券类因子 (新建)

**新建**: `backend/app/services/features/bond_features.py`

核心因子：
- **物理先验特征**: `-久期 × Δ10Y国债收益率`（直接编码为特征）
- 利率曲线：10Y/1Y/2Y收益率日变动、期限利差(10Y-2Y)、曲线斜率变化
- 信用利差：AAA/AA+ 企业债利差、城投债利差、利差日变动
- 流动性：DR007、DR007 vs MLF偏离、Shibor变化、OMO净投放
- 宏观：CPI/PPI、社融超预期程度

**久期估算**（数据缺失时的替代方案）：

```python
# 当无法获取基金久期数据时，按类型估算
DURATION_ESTIMATE = {
    "bond_pure": 3.0,         # 纯债久期约3年
    "bond_mixed": 2.5,        # 混合债久期约2.5年
    "bond_convertible": 1.5,  # 可转债久期较短
}
```

#### 2.3 指数/ETF 规则引擎 (新建)

**新建**: `backend/app/services/rules/index_rule_engine.py`

不需要 ML 训练，直接用规则公式：

```python
def predict_index_fund(fund_code, benchmark_index):
    # 核心公式：T+1 净值 ≈ T日净值 × (1 + 标的指数T+1日涨跌幅 × 跟踪倍率 - 日管理费)
    index_return = get_index_return(benchmark_index)
    tracking_multiplier = 1.0  # 非杠杆ETF
    daily_fee = 0.000003  # 约0.0003%/日
    pred_nav = today_nav * (1 + index_return * tracking_multiplier - daily_fee)
    
    # ML校准层：用LightGBM校正少量跟踪误差
    correction = tracking_error_model.predict(features)
    return pred_nav + correction
```

#### 2.4 灵活配置两阶段 (新建)

**新建**: `backend/app/services/pipelines/flexible_pipeline.py`

```python
def predict_flexible(fund_code):
    # 阶段1：滚动Beta估算当前仓位
    # 仓位 ≈ corr(基金收益, 沪深300收益) × std(基金)/std(沪深300)
    estimated_position = estimate_position_rolling_beta(fund_code, window=10)
    
    # 阶段2：动态加权预测
    if estimated_position > 0.6:
        return equity_model.predict(features, weight=estimated_position)
    elif estimated_position < 0.3:
        return bond_model.predict(features, weight=1-estimated_position)
    else:
        equity_pred = equity_model.predict(features)
        bond_pred = bond_model.predict(features)
        return equity_pred * estimated_position + bond_pred * (1 - estimated_position)
```

---

### 阶段 3：模型选型与集成增强

#### 3.1 添加 LSTM/Transformer 模型 (可选，根据资源决定)

**新建**: `backend/app/services/models/deep_models.py`

- LSTM：捕捉时序依赖，输入为最近60日的特征序列
- 如果资源有限，可先跳过，仅使用 LightGBM + XGBoost 集成

#### 3.2 三层集成架构

**修改**: `backend/app/services/model_selection_service.py`

```
Layer1（基础模型）:
  - LightGBM (已有)
  - XGBoost (已有)
  - RandomForest (已有)
  - ExtraTrees (已有)
  - HistGBR (已有)
  - Ridge (已有)
  - ElasticNet (已有)

Layer2（Stacking）:
  - 用 Ridge 对 Layer1 输出做线性组合
  - 在验证集上学习各模型的优势区间权重

Layer3（残差自适应修正）:
  - 基于最近 10 个交易日的预测误差
  - 简单移动平均修正系统偏误
```

#### 3.3 Walk-Forward 时序交叉验证

**修改**: `backend/app/services/model_selection_service.py`

替换现有的固定划分，改用滚动验证：

```python
def walk_forward_validation(df, train_months=24, valid_months=3, step_months=1, min_rounds=12):
    """时序滚动交叉验证"""
    results = []
    n = len(df)
    train_size = int(train_months * 21)  # ~21 交易日/月
    valid_size = int(valid_months * 21)
    step_size = int(step_months * 21)
    
    for start in range(0, n - train_size - valid_size, step_size):
        train = df.iloc[start:start + train_size]
        valid = df.iloc[start + train_size:start + train_size + valid_size]
        if len(valid) < 20:
            break
        # 训练并评估...
        results.append(...)
    
    return aggregate_results(results)
```

#### 3.4 样本时间权重

```python
# 在训练时给近期样本更高权重
halflife = 60  # 半衰期 60 个交易日
weights = np.exp(-np.log(2) * np.arange(n-1, -1, -1) / halflife)
model.fit(X, y, sample_weight=weights)
```

---

### 阶段 4：预测后处理增强

#### 4.1 Conformal Prediction 置信区间

**新建**: `backend/app/services/postprocessing/conformal.py`

```python
def conformal_interval(model, X_calib, y_calib, X_new, alpha=0.1):
    """保形预测：生成 coverage 保证的预测区间
    
    1. 在 calib 集上计算非一致性得分 s_i = |y_i - ŷ_i|
    2. 取 s_i 的 (1-alpha) 分位数作为阈值
    3. 对新样本输出 [ŷ - threshold, ŷ + threshold]
    """
    calib_pred = model.predict(X_calib)
    scores = np.abs(y_calib - calib_pred)
    threshold = np.quantile(scores, 1 - alpha)
    new_pred = model.predict(X_new)
    return new_pred - threshold, new_pred + threshold
```

#### 4.2 预测值约束规则

```python
# 按基金类型的净值变动约束
NAV_CONSTRAINTS = {
    "hybrid_equity": 0.20,     # ±20%
    "equity_active": 0.20,
    "hybrid_balanced": 0.15,
    "hybrid_bond": 0.10,
    "bond_pure": 0.05,         # ±5%
    "bond_mixed": 0.08,
    "bond_convertible": 0.20,  # 可转债有涨跌停
    "index_equity": None,       # 跟随标的指数
}

def apply_constraints(pred_return, fund_type):
    limit = NAV_CONSTRAINTS.get(fund_type)
    if limit is not None:
        return np.clip(pred_return, -limit, limit)
    return pred_return
```

#### 4.3 特殊时期置信度调整

```python
def adjust_confidence(asof_date, fund_type, fund_profile):
    adjustments = []
    
    # 季报窗口（3/6/9/12月末前后10日）
    if is_report_window(asof_date):
        adjustments.append(("report_window", -0.15))
    
    # 重大政策发布日
    if is_policy_day(asof_date):
        adjustments.append(("policy_day", -0.20))
    
    # 市场极端波动日（前日涨跌幅 > ±3%）
    if abs(prev_day_return) > 0.03:
        adjustments.append(("extreme_volatility", -0.10))
    
    # 长假前后
    if is_holiday_adjacent(asof_date):
        adjustments.append(("holiday_effect", -0.10))
    
    # 基金经理变更后3个月内
    if manager_changed_recently(fund_profile, asof_date):
        adjustments.append(("manager_change", -0.25))
    
    return adjustments
```

---

### 阶段 5：模型更新与监控策略

#### 5.1 每日自动化更新流程

```python
# 08:00 - 拉取前日净值，更新历史特征矩阵
async def morning_update():
    for fund_code in active_funds:
        update_nav_history(fund_code)
        update_feature_matrix(fund_code)
        record_prediction_accuracy(fund_code)

# 09:00 - 完成 T+1 日预测
async def morning_prediction():
    for fund_code in active_funds:
        prediction = predict_t_plus_1(fund_code)
        store_prediction(prediction)

# 15:00 收盘后 - 更新 T+1 预测（用当日收盘数据）
async def after_close_update():
    for fund_code in active_funds:
        update_with_today_close(fund_code)

# 21:00 - 净值公布后，计算预测误差，检查监控指标
async def evening_validation():
    for fund_code in active_funds:
        actual_nav = fetch_today_nav(fund_code)
        error = calculate_error(predicted_nav, actual_nav)
        check_monitoring_thresholds(fund_code, error)
```

#### 5.2 模型退化监控

```python
def check_model_degradation(fund_code):
    recent_errors = get_recent_errors(fund_code, days=20)
    
    alerts = []
    # 1. 当日 MAE 超过历史均值 2σ
    if recent_errors[-1]["mae"] > historical_mae_mean + 2 * historical_mae_std:
        alerts.append(Alert("MAE_OUTLIER", severity="warning"))
    
    # 2. 连续5日方向准确率 < 50%
    if direction_accuracy(recent_errors[-5:]) < 0.5:
        alerts.append(Alert("DIRECTION_DEGRADED", severity="warning"))
    
    # 3. 预测残差单向偏斜
    if abs(np.mean([e["residual"] for e in recent_errors[-10:]])) > threshold:
        alerts.append(Alert("SYSTEMATIC_BIAS", severity="critical"))
    
    # 自动触发重训
    if any(a.severity == "critical" for a in alerts):
        schedule_retraining(fund_code)
    
    return alerts
```

---

### 阶段 6：冷启动与持仓时效管理

#### 6.1 新基金冷启动

```python
def cold_start_strategy(fund_code, fund_profile):
    nav_days = get_nav_history_days(fund_code)
    
    if nav_days < 60:  # 成立不足3个月
        # 使用同类型基金的群体模型
        return group_model.predict(fund_profile.type, features)
    
    elif nav_days < 120:  # 3-6个月
        # 群体模型 + 少量个体微调
        group_pred = group_model.predict(fund_profile.type, features)
        individual_correction = fine_tune_model.predict(features)
        return group_pred + 0.3 * individual_correction
    
    else:  # 6个月以上
        return individual_model.predict(features)
```

#### 6.2 持仓数据时效性管理

```python
def manage_holding_freshness(fund_code):
    holding_age = days_since_last_report(fund_code)
    
    if holding_age <= 28:  # 披露后4周内
        holding_weight = 1.0
        index_weight = 0.3
    elif holding_age <= 56:  # 5-8周
        holding_weight = 0.7
        index_weight = 0.6
    else:  # 9周以上
        holding_weight = 0.3
        index_weight = 1.0
    
    # 持仓漂移检测：净值与持仓映射结果偏差持续 > 1%
    if detect_holding_drift(fund_code):
        holding_weight = 0.0
        index_weight = 1.0
    
    return holding_weight, index_weight
```

---

### 阶段 7：T日盘中净值估算（新功能）

#### 7.1 双路径融合估算

**新建**: `backend/app/services/intraday_estimation.py`

```python
def estimate_intraday_nav(fund_code, fund_profile):
    # 路径A：持仓映射（有持仓数据时优先）
    if fund_profile.has_recent_holdings():
        holding_estimate = map_holdings_to_realtime(fund_code)
        holding_weight = get_holding_freshness_weight(fund_code)
    else:
        holding_estimate = None
        holding_weight = 0
    
    # 路径B：指数回归（全天候适用）
    index_estimate = regression_estimate_from_indices(fund_code, fund_profile)
    index_weight = 1 - holding_weight
    
    # 动态融合：用近30日各路径误差调整权重
    if holding_estimate and index_estimate:
        holding_error = get_recent_error(fund_code, "holding_path", days=30)
        index_error = get_recent_error(fund_code, "index_path", days=30)
        total = holding_error + index_error
        holding_weight = index_error / total
        index_weight = holding_error / total
    
    return combine_estimates(holding_estimate, index_estimate, holding_weight, index_weight)
```

---

### 阶段 8：工程规范与部署

#### 8.1 Docker 部署

**新建**: `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
```

**新建**: `docker-compose.yml`
```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
      - ./output:/app/output
    environment:
      - LOG_LEVEL=INFO
```

#### 8.2 异常 HTTP 状态码映射

**修改**: `backend/app/core/errors.py` — 为每个 AppError 子类添加 `http_status` 属性

**修改**: `backend/app/main.py` — 使用 `exc.http_status` 替代写死的 `400`

#### 8.3 异步任务队列

引入 Celery + Redis 或 ARQ，替代当前的 BackgroundTasks。

#### 8.4 API 版本化

添加 `/api/v1/` 前缀，通过路由别名兼容老路径。

#### 8.5 单元测试

```
tests/
  unit/
    test_fund_profile.py      # 基金分类逻辑
    test_data_service.py      # 数据获取、缓存
    test_feature_service.py   # 特征构建、泄露检测
    test_model_selection.py   # Walk-Forward、模型选择
    test_conformal.py         # 保形预测
    test_constraints.py       # 约束规则
    test_routing.py           # 分类路由
  integration/
    test_e2e_equity.py        # 偏股基金端到端
    test_e2e_bond.py          # 债券基金端到端
    test_e2e_index.py         # 指数基金端到端
```

---

### 阶段 9：T 日盘中估算前端 (新增页面)

**新建**: `static/intraday.html` + `static/assets/intraday.js`

功能：
- 实时显示盘中估算净值
- 展示持仓映射路径 vs 指数回归路径的融合权重
- 净值公布后自动对比估算结果
- 可视化盘中净值走势

---

### 阶段 10：多步预测与 FOF 递归

#### 10.1 多步预测（3日/5日）

```python
def predict_multi_step(fund_code, steps=[1, 3, 5]):
    predictions = {}
    for step in steps:
        if step == 1:
            predictions[1] = predict_t_plus_1(fund_code)
        else:
            # 迭代预测：用预测值作为下一天的输入
            predictions[step] = iterative_predict(fund_code, step)
            # 误差随步长增大，扩大置信区间
            predictions[step]["interval_width"] *= np.sqrt(step)
    return predictions
```

#### 10.2 FOF 递归预测

```python
def predict_fof(fund_code):
    sub_funds = get_fof_holdings(fund_code)
    sub_predictions = {}
    for sub_code, weight in sub_funds.items():
        # 递归调用主预测流程
        sub_predictions[sub_code] = predict_fund(sub_code)
    
    # 按持仓权重加权汇总
    fof_prediction = weighted_average(sub_predictions)
    return fof_prediction
```

---

## 三、实施优先级汇总

| 阶段 | 内容 | 优先级 | 预计工作量 | 前置依赖 |
|------|------|--------|-----------|---------|
| 阶段 0 | P0 致命问题修复 | P0 | 1-2天 | 无 |
| 阶段 1 | 基金画像与分类路由 | P0 | 3-5天 | 阶段0 |
| 阶段 2.1 | 偏股类因子增强 + 预筛选 | P1 | 3-5天 | 阶段1 |
| 阶段 2.2 | 债券类因子 + 物理先验 | P1 | 3-5天 | 阶段1 |
| 阶段 2.3 | 指数/ETF 规则引擎 | P1 | 2-3天 | 阶段1 |
| 阶段 2.4 | 灵活配置两阶段 | P1 | 2-3天 | 阶段1 |
| 阶段 3.1 | 模型集成 (Layer1+2) | P1 | 3-5天 | 阶段2 |
| 阶段 3.2 | Walk-Forward 交叉验证 | P1 | 2-3天 | 阶段2 |
| 阶段 3.3 | 样本时间权重 | P1 | 1天 | 阶段2 |
| 阶段 4 | 后处理增强 | P1 | 3-5天 | 阶段3 |
| 阶段 5 | 自动化更新 + 监控 | P2 | 5-7天 | 阶段4 |
| 阶段 6 | 冷启动 + 持仓时效 | P2 | 3-5天 | 阶段1 |
| 阶段 7 | T日盘中估值 | P2 | 5-7天 | 阶段2 |
| 阶段 8 | 工程规范 | P2 | 3-5天 | 无 |
| 阶段 9 | 前端增强 | P2 | 3-5天 | 阶段7 |
| 阶段 10 | 多步预测 + FOF | P3 | 3-5天 | 阶段4 |

---

## 四、风险与回滚策略

1. **每次阶段完成后做功能验证**：确保已有功能（偏股基金预测）不被破坏
2. **新基金类型先作为 beta 功能**：默认走原有通用流水线，通过参数开启新流水线
3. **数据获取失败降级**：外部 API 不可用时使用缓存数据
4. **模型训练失败降级**：保留上一版本模型继续服务
5. **所有新文件遵循现有项目结构**：不破坏现有目录组织

---

*本计划基于 `fund_nav_prediction_strategy.md` v1.0 和 2026年5月24日代码审查生成。*