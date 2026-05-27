# 预测模型逻辑与性能审计报告

> 日期: 2026-05-24 | 范围: 预测、路由、模型注册、特征对齐 | 不改代码，仅分析

---

## Why

用户发现 profile 数据失实后，担心预测模型也可能存在类似的逻辑错误或性能问题。本次审计覆盖预测全链路：`prediction_service → routing_service → model_registry → feature_service → model_selection` 中与预测产出直接相关的环节。

---

## 分析范围

| 文件 | 行数 | 核心功能 |
|------|------|---------|
| [prediction_service.py](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py) | 482 | 主预测入口 `predict_next` |
| [routing_service.py](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/routing_service.py) | 60 | `route_predict` 分类路由 |
| [model_registry_service.py](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_registry_service.py) | 157 | 模型存档/加载/预测历史 |
| [feature_service.py](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/feature_service.py) | 285+ | `model_feature_columns` / `build_features` |
| [model_selection_service.py](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py) | 810+ | `_point_model` / `_direction_model` / `_regime_intervals` |

---

## 发现总览

共发现 **16 个问题**，按严重度分为：

| 严重度 | 数量 | 含义 |
|--------|------|------|
| 🔴 逻辑缺陷 | 6 | 可能导致错误预测结果或静默失败 |
| 🟡 性能问题 | 5 | 增加延迟/资源消耗 |
| 🟠 设计问题 | 5 | 不直接影响正确性但降低可维护性/可扩展性 |

---

## 🔴 逻辑缺陷（Critical Logic Issues）

### 1. 缺失特征被静默填充为 0.0，产生无意义的预测

**位置**: [`_align_model_features` L169-176](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L169-L176)

```python
def _align_model_features(model, latest, fallback_cols):
    cols = _model_feature_names(model, fallback_cols)
    aligned = latest.copy()
    for col in cols:
        if col not in aligned.columns:
            aligned[col] = 0.0    # ← 危险！
    aligned = aligned[cols].fillna(0.0)
    return aligned
```

**问题**: 当模型需要某个特征列（如 `cyb_ret_mean_5`），但预测时 `latest` DataFrame 中不存在该列时，直接填 0.0。

**实际影响**: 创业板指数数据获取经常失败（ProxyError），导致 `cyb_ret` 及相关衍生特征全部缺失。模型在训练时看到的是真实波动值（如 `cyb_ret_mean_5 = +0.02`），但预测时得到的是 0.0。对于依赖该特征的模型（如 xgboost 的 `feature_importance` 较高的特征），这会产生完全错误的预测。

**严重度**: 🔴 高。这是一个静默失败——不会报错，但预测值可能是错的。

**建议修复方向**: 
- 填充前记录缺失列并设置 `feature_quality_flag = "degraded_critical"`
- 如果关键特征缺失（importance > threshold），拒绝预测并返回错误，而不是填 0
- 在训练日志中记录每个特征的缺失频率，提醒用户网络问题会显著影响特定特征可用性

---

### 2. proxy_quality_flag 为 NaN 时未正确降级

**位置**: [`predict_next` L255](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L255)

```python
proxy_quality = latest["proxy_quality_flag"].iloc[0] if "proxy_quality_flag" in latest.columns else "low"
```

**问题**: 条件只检查列名是否存在于 DataFrame 中，不检查值是否为 NaN。当 `proxy_quality_flag` 列存在但 proxy portfolio 服务失败时，该列的值是 NaN（由 `proxy_portfolio_service` 在计算失败时产生）。

**实际影响**: `proxy_quality` 变量携带 NaN，传给 `append_prediction` 后被写入 CSV，导致 `prediction_history.csv` 中该列为 NaN。下游分析（如模型监控）在处理 NaN 时可能报错。

**严重度**: 🔴 中。不会导致预测错误，但会产生脏数据。

**建议修复方向**: `val = latest["proxy_quality_flag"].iloc[0]; proxy_quality = val if isinstance(val, str) else "low"`

---

### 3. missing_rate 基于全量特征而非模型实际使用的特征

**位置**: [`predict_next` L197-206](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L197-L206)

```python
feature_cols = model_feature_columns(data_full)  # 返回所有特征(如191个)
latest = data_full.iloc[[-1]]
missing_rate = float(latest[feature_cols].isna().mean(axis=1).iloc[0])  # 基于191个特征
if missing_rate > 0.35:
    logger.warning(...)  # 仅警告
```

**问题**: `model_feature_columns` 返回所有可用特征（约 191 个），但模型经过选择器（如 `f_top20`）后实际只用了 20 个。`missing_rate` 在 191 个特征上计算，但模型只关心其中 20 个。

**实际场景**:
- 真实情况 A: 模型需要的 20 个特征中 10 个缺失（50%）→ missing_rate 只在 191 个中显示了 10/191 ≈ 5% — **不会警告，但预测质量极差**
- 真实情况 B: 次要特征缺失（如 `zz1000_ret_mean_60`），模型根本没用到 → missing_rate 触发警告，但预测完全正常 — **虚惊一场**

**严重度**: 🔴 中。产生误导性的质量信号。

**建议修复方向**: `missing_rate` 改为基于模型实际使用的特征（用 `_model_feature_names` 获取）而非全量特征。

---

### 4. 方向模型校准后的概率与信号阈值的语义不一致

**位置**: [`_direction_signal` L17-28](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L17-L28) + [`_direction_model` L612](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L612)

```python
# 训练时的标签：上涨 vs 下跌(二分类)
y_train = (train_base["target_next"] > 0).astype(int)

# 预测时的信号：多级阈值
if p_up >= 0.65:  return "bullish", "strong"
if p_up >= 0.60:  return "bullish", "weak"
if p_up <= 0.35:  return "bearish", "strong"
if p_up <= 0.40:  return "bearish", "weak"
return "neutral", "none"
```

**问题**: 

1. **阈值不对称缺乏依据**: bullish strong 需要 p_up ≥ 0.65（上涨概率 ≥ 65%），但 bearish strong 需要 p_up ≤ 0.35（即下跌概率 ≥ 65%）。如果市场本身有上涨偏斜（比如牛市中 55% 的交易日上涨），65% 的 threshold 对双向都是不合理的——bullish 很难触发，bearish 更不可能触发。

2. **CalibratedClassifierCV 产出的概率未必在自然场景下校准**: 校准是在训练集上做的，但分布偏移（regime shift）可能导致预测时的概率不再校准。当前代码未检测校准漂移。

**严重度**: 🔴 中。在强趋势市场中，信号会偏向 neutral，失去参考价值。

---

### 5. 方向模型只训练在 train_base+valid 的 fit_part/calib_part 上，未利用 test_select 数据

**位置**: [`_direction_model` L636-649](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L636-L649)

```python
train_valid = pd.concat([train_base, valid])   # 去掉了 test_select
calib_size = max(60, int(len(train_valid) * 0.2))
fit_part = train_valid.iloc[:-calib_size]       # train_base+valid的前80%
calib_part = train_valid.iloc[-calib_size:]      # train_base+valid的后20%
```

对比点模型（[`_point_model` L467-468](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L467-L468)）：
```python
final_pipe.fit(data_train[feature_cols], data_train["target_next"])
# ↑ data_train = train_base + valid + test_select — 使用了全部训练数据
```

**问题**: 点模型最终在全量 `data_train`（train_base + valid + test_select）上重新训练，而方向模型的 `final` 阶段只用了 `train_base + valid`（fit_part + calib_part = train_valid）。`test_select` 的 40 行数据未用于方向模型的最终训练。

**实际影响**: 方向模型少了约 40 行训练数据（约 8% 的训练集），在高数据量环境下影响较小，但对于低数据量场景可能降低方向预测精度。

**严重度**: 🔴 低。数据量级下影响有限，但不一致的设计容易导致后续维护者混淆。

---

### 6. prediction_history.csv 写入存在竞态条件

**位置**: [`append_prediction` L150-154](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_registry_service.py#L150-L154)

```python
def append_prediction(fund_code, row):
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    out = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
    out.to_csv(path, index=False)
```

**问题**: 读-改-写三步操作无任何锁机制。如果两个用户同时请求 `/predict`（或前端快速双击），写操作会交错：

```
进程A: read_csv → 得到 10 行
进程B: read_csv → 也得到 10 行
进程A: concat 11行 → write_csv → 写入 11 行
进程B: concat 11行 → write_csv → 覆盖为 11 行  ← 进程A的预测丢失！
```

**严重度**: 🔴 低。多用户场景不常见，但一旦发生数据静默丢失无法恢复。

---

## 🟡 性能问题

### 7. append_prediction 每次 O(n) 文件 I/O

**位置**: 同上 [L150-154](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_registry_service.py#L150-L154)

**问题**: 每次预测都完整读取 CSV 文件（n 行），concat 后完整写回。100 次预测 = 100 × read_all + 100 × write_all。

**量级**: 假设积累 500 条预测记录，每次预测额外开销：
- 读 500 行 CSV（含 40 列）≈ 2ms
- concat + write 501 行 ≈ 3ms
- 总计每次预测额外 5ms，看似不大，但随预测数线性增长。1000 次后 = 10ms/次。

**建议修复方向**: 改用 `mode='a'` 追加写入（不需要读取旧数据），或以 SQLite `prediction_history` 表替代 CSV。

---

### 8. _clean_nan 对 50+ 键的递归遍历每次预测都执行

**位置**: [`_clean_nan` L121-139](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L121-L139) → [`predict_next` L388](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L388)

**问题**: 预测结果 dict 有 50+ 个顶层键，部分嵌套（`baseline`、`intervals`、`nav_interval_*`、`excess_signals` 中的嵌套 dict）。`_clean_nan` 递归遍历所有 dict/list，检查每个 float 是否为 NaN。这在 Python 中是纯 CPU 操作，不可并行。

**量级**: 50 键 × 2 层嵌套 × 检查开销 ≈ 0.5-1ms。看起来不大，但这不是预测的核心计算，而是后处理。

**建议修复方向**: 在数据构造阶段就确保不引入 NaN（用 `_safe_float` 的统一包装 + `defaultdict`），可以省去整个递归清理步骤。或者将 `_safe_float` 用在所有可能产生 NaN 的赋值点。

---

### 9. 方向模型 84 候选的校准横穿整个 valid 集

**位置**: [`_direction_model` L618-626](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L618-L626)

```python
for model_name, selector, scaler, model in _candidates(_classifiers()):
    # 84 iterations
    base = _make_pipeline(...)
    base.fit(train_base[feature_cols], y_train)
    calibrated = _calibrated_direction_pipeline(base, valid[feature_cols], y_valid)
    # ↑ 每个候选都在 valid 上做 CalibratedClassifierCV
```

**问题**: `_calibrated_direction_pipeline` 内部是 `CalibratedClassifierCV`，它执行 5-fold 交叉验证。84 候选 × 5 fold × valid 集 = 420 次 `fit` 调用。这在 train.log 中表现为 84 条 `calibration_start → calibration_success` 日志。

**量级**: 以 022771 为例，train.log 显示 direction model train start 到 model_selection 耗时约 26 秒（22:10:17 → 22:10:43），其中大部分花在 84 次校准上。

**建议修复方向**: rough 阶段不用 CalibratedClassifierCV，仅计算 `predict_proba`（无校准），用 Brier score 排序后保留 top-10 再校准。

---

### 10. _rolling_baselines 重复计算

**位置**: [`_point_model` L294-295](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L294-L295)

```python
baselines_select = _rolling_baselines(data_train, test_select)  # 计算1
baselines_final = _rolling_baselines(data_train, test_final)    # 计算2
```

此外方向模型在 `select_and_train` L634 附近也可能再次计算。`_rolling_baselines` 对 data_train 做 rolling 窗口计算（O(len × window)），每次约 500×20 = 10,000 次均值计算。

**建议修复方向**: 对 data_train 一次性计算完整的 rolling mean/std，然后按日期索引取 test_select/test_final 行的子集。

---

### 11. pd.concat + to_csv 对大 CSV 的不断膨胀

**位置**: [`append_prediction` L152-154](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_registry_service.py#L152-L154)

同问题 #7，但侧重不同：`concat` 操作涉及全量 DataFrame 复制（O(n) 内存），不是简单的 append。

---

## 🟠 设计问题

### 12. route_predict 是空路由——所有类型走同一个流水线

**位置**: [`route_predict` L31-47](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/routing_service.py#L31-L47)

```python
if profile.fund_type in ("hybrid_equity", "equity_active"):
    result = generic_predict(...)
elif profile.fund_type == "index_equity":
    result = generic_predict(...)  # ← 也是同一个函数
else:
    result = generic_predict(...)  # ← 债券/FOF/QDII 也是同一个
```

**问题**: 路由器存在但没有路由效果。所有非货币基金类型全部走 `generic_predict`。对于债券基金/FOF/QDII，用权益类模型预测收益率预测效果存疑。

**现状**: 代码注释写明"阶段1：偏股类走现有成熟流程；其他类型走通用流程"，说明这是有意为之的渐进式设计。但当前所有类型事实上一视同仁，`route_predict` 对结果无任何差异化处理。

---

### 13. 方向信号阈值不对称且无文档说明

**位置**: [`_direction_signal` L20-27](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L20-L27)

```python
if p_up >= 0.65: bullish/strong     # 上涨≥65%是强信号
if p_up >= 0.60: bullish/weak       # 上涨60-64%是弱信号
if p_up <= 0.35: bearish/strong     # 下跌≥65%是强信号
if p_up <= 0.40: bearish/weak       # 下跌60-64%是弱信号
```

**问题分析**:
- **bullish weak 区间**: [0.60, 0.65) → 宽度 5%
- **bearish weak 区间**: (0.35, 0.40] → 宽度 5%
- **neutral 区间**: (0.40, 0.60) → 宽度 20%
- **不对称性**: 为什么 bullish strong = 0.65 而 bearish strong = 0.35？这不是对称的——如果公平校准，应该 bullish = p_up ≥ 0.5 + x, bearish = p_up ≤ 0.5 - x。当前 bullish strong 偏离 0.15 但 bearish strong 也偏离 0.15，这是对称的。但为什么选 0.15？无依据。

---

### 14. 区间宽度健康检查用绝对阈值

**位置**: [`_intervals` L100](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L100)

```python
health = "normal" if width80 < 0.05 else "wide" if width80 < 0.08 else "very_wide"
```

**问题**: 不同基金的波动率差异很大：
- 货币基金：日收益 0.0001，宽度 0.05 = 100bp → **超级宽**
- 高波动股票基金：日收益 ±0.02，宽度 0.05 = 100bp → 正常

同样 0.05 (100bp) 对不同基金的含义完全不同。应该用相对度量（如 `width / fund_ret_std_20`）。

---

### 15. 区间估计算法基于残差绝对值分位数——这是一个合理但粗糙的近似

**位置**: [`_regime_intervals` L682](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L682)

```python
global_q = {str(q): float(np.quantile(abs_resid, q / 100)) for q in [70, 80, 90, 99]}
```

**分析**: 使用 `abs(residual)` 的分位数作为区间半径。这意味着：
- 假设残差分布是对称的（`pred ± radius`）
- 不考虑残差的异方差性（宽度随波动率放大，这一点通过分组 quantiles 部分缓解）
- 分位数方法本身是合理的非参数区间估计

**问题**: 该方法在低样本量下分组 quantile 不可用（`fallback=True`），回退到全局 quantile。全局 quantile 对所有波动率区间一视同仁，低波动期区间偏宽，高波动期区间偏窄。

**状态**: 这是方法学上的权衡，不是代码 bug。如果追求更精确的区间估计，可考虑 conformal prediction 或 GARCH 模型。

---

### 16. direction_backtest["p_up"] 与 predict_next 中的 p_up 使用不同来源

**位置**:
- 回测阶段: [`model_selection_service.py L806-807`](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/model_selection_service.py#L806-L807) — `direction_backtest["p_up"] = p_test` (来自方向模型对 test_final 的预测)
- 预测阶段: [`prediction_service.py L225`](file:///home/joakim/Project/fund_project/fund_predictor/backend/app/services/prediction_service.py#L225-L226) — `p_up = float(proba[direction_classes.index(1)])`

**分析**: 回测时 `p_test` 是方向模型在训练完成后立即对 `test_final` 生成的预测。但实际部署预测时，模型可能因为数据分布偏移产生不同的概率估计。两者之间的差异没有监控。

**状态**: 这是一个"训练-服务偏差"（train-serve skew）的潜在来源，目前没有被系统性地追踪。建议在模型监控中对比历史预测概率和回测概率的分布差异。

---

## 汇总表

| # | 类别 | 问题 | 文件 | 行号 |
|---|------|------|------|------|
| 1 | 🔴 逻辑 | 缺失特征被静默填0 | prediction_service.py | L173-174 |
| 2 | 🔴 逻辑 | proxy_quality_flag NaN未降级 | prediction_service.py | L255 |
| 3 | 🔴 逻辑 | missing_rate基于全量而非模型实际特征 | prediction_service.py | L199 |
| 4 | 🔴 逻辑 | 方向信号阈值与校准概率语义不一致 | prediction_service.py | L20-27 |
| 5 | 🔴 逻辑 | 方向模型未在test_select上重新训练 | model_selection_service.py | L636-638 |
| 6 | 🔴 逻辑 | prediction_history竞态条件 | model_registry_service.py | L150-154 |
| 7 | 🟡 性能 | append_prediction O(n) I/O | model_registry_service.py | L150-154 |
| 8 | 🟡 性能 | _clean_nan递归遍历 | prediction_service.py | L121-139 |
| 9 | 🟡 性能 | 84候选×5fold校准 | model_selection_service.py | L618-626 |
| 10 | 🟡 性能 | _rolling_baselines重复计算 | model_selection_service.py | L294-295 |
| 11 | 🟡 性能 | concat CSV全量复制 | model_registry_service.py | L152 |
| 12 | 🟠 设计 | route_predict是空路由 | routing_service.py | L31-47 |
| 13 | 🟠 设计 | 方向信号阈值无依据 | prediction_service.py | L20-27 |
| 14 | 🟠 设计 | 区间宽度健康检查用绝对阈值 | prediction_service.py | L100 |
| 15 | 🟠 设计 | 残差分位数区间在低样本下fallback粗糙 | model_selection_service.py | L682-683 |
| 16 | 🟠 设计 | train-serve skew无监控 | prediction_service.py | L225 |

---

## 未发现问题的方面

以下方面经过审计后确认 **没有逻辑问题**：

- ✅ **数据泄露防护**: `model_feature_columns` 正确排除了 `target_next`、`target_date`、`target_excess_*` 等未来标签列。`build_features` 通过 `dropna(subset=["target_next"])` 只对训练数据过滤，保留完整 DataFrame 供预测取最后一行。
- ✅ **点模型在 full data 上重训**: `final_pipe.fit(data_train, ...)` 在 train_base+valid+test_select 全量上训练，test_final 始终未参与训练。
- ✅ **区间估计的 regime_thresholds**: `_current_regime` 的逻辑正确——`vol <= q33 → low_vol`、`vol >= q66 → high_vol`、其余 mid_vol。
- ✅ **p_down 回退计算**: 当方向模型不可用或失败时，`p_down = 1 - p_up` 保证概率自洽。
- ✅ **_model_feature_names 的多层回退**: 遍历 pipeline → estimator → estimator.estimator 查找 `feature_names_in_`，覆盖了大部分 sklearn pipeline 场景。