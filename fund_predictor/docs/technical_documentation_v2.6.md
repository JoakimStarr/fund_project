# 基金 T+1 净值涨跌幅区间预测系统 — 技术文档

> 版本: v2.6.0 | 更新: 2026-05-25  
> 本文档完整描述系统的架构、数据流、计算逻辑、判断分支和配置参数。  
> **新增**: GPU加速支持 (XGBoost/LightGBM)

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [目录结构与模块依赖](#2-目录结构与模块依赖)
3. [数据获取详细流程](#3-数据获取详细流程)
4. [特征工程详细流程](#4-特征工程详细流程)
5. [基金分类路由系统](#5-基金分类路由系统)
6. [因子预筛选](#6-因子预筛选)
7. [模型训练与选择](#7-模型训练与选择)
8. [集成学习（Stacking）](#8-集成学习stacking)
9. [后处理：保形预测与净值约束](#9-后处理保形预测与净值约束)
10. [冷启动机制](#10-冷启动机制)
11. [API 接口规范](#11-api-接口规范)
12. [配置参数手册](#12-配置参数手册)
13. [前端架构](#13-前端架构)
14. [日志系统](#14-日志系统)
15. [端到端完整数据流](#15-端到端完整数据流)

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue3 + Vite)                    │
│  Predict / Train / Backtest / Dashboard / Intraday / ...   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (axios, baseURL=/api/v1)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI 后端                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Fund API │  │ Train API│  │Task API  │  │Backtest  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│       ▼              ▼              ▼              ▼          │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Routing Service (路由引擎)            │      │
│  │  classify_fund() → fund_type → pipeline           │      │
│  └────────────────────┬─────────────────────────────┘      │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────┐      │
│  │            Prediction Service (预测核心)           │      │
│  │                                                    │      │
│  │  数据获取 → 特征构建 → 因子筛选 → 模型训练         │      │
│  │        → Stacking集成 → 保形区间 → 净值约束        │      │
│  └──────────────────────────────────────────────────┘      │
│                       │                                    │
│  ┌────────────────────┴─────────────────────────────┐      │
│  │  Cold Start | Intraday | FOF | Hyperopt | Cache   │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据存储层                                  │
│  SQLite (WAL) │ CSV (raw/processed) │ Joblib (.pkl)          │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI + Uvicorn (Python 3.11+) |
| 前端框架 | Vue 3 + Vite + Element Plus + ECharts |
| 数据存储 | SQLite WAL模式 + CSV文件 + Joblib模型序列化 |
| 机器学习 | scikit-learn + Ridge/ElasticNet/LGBM/XGBoost |
| 统计方法 | Conformal Prediction (保形预测), Walk-Forward CV |
| 部署 | Docker Compose (backend + nginx frontend) |

---

## 2. 目录结构与模块依赖

```
fund_predictor/
├── config.yaml                    # 全局配置（~158行，集中管理所有参数）
├── backend/app/
│   ├── main.py                    # 入口：FastAPI应用、中间件、路由注册
│   ├── core/
│   │   ├── config.py              # 配置加载器（YAML → 常量导出）
│   │   ├── logging_config.py      # 日志系统（6种Handler + JSONL）
│   │   ├── errors.py              # 异常体系（HTTP状态码映射）
│   │   ├── perf_logger.py         # 性能日志装饰器
│   │   └── audit_logger.py        # 审计日志封装
│   ├── api/                       # 6个路由模块（RESTful）
│   │   ├── fund.py                # POST /predict, GET /{code}/profile
│   │   ├── train.py               # POST /train (异步任务)
│   │   ├── task.py                # GET /tasks, GET /tasks/{id}
│   │   ├── model.py               # GET /health
│   │   ├── backtest.py            # GET /health
│   │   ├── intraday.py            # POST /{code}/intraday
│   │   └── dashboard.py           # GET /stats, /recent-predictions
│   ├── services/                  # 业务逻辑层
│   │   ├── routing_service.py     # 路由：fund_type → pipeline
│   │   ├── prediction_service.py  # 预测主流程编排
│   │   ├── data_service.py        # 数据获取（缓存+并发+fallback）
│   │   ├── feature_service.py     # 特征构建（lag/rolling/beta/style）
│   │   ├── model_selection_service.py  # 四段划分 + 模型评估
│   │   ├── task_service.py        # 异步任务队列
│   │   ├── fund_profile_service.py    # 三级分类（type→benchmark→default）
│   │   ├── cold_start.py          # 冷启动群体模型
│   │   ├── features/
│   │   │   ├── factor_screening.py    # IC/VIF/ICIR筛选
│   │   │   ├── ensemble.py            # Stacking Ridge集成
│   │   │   ├── enhanced_equity_features.py  # 股票增强特征
│   │   │   ├── bond_features.py       # 债券物理先验特征
│   │   │   └── macro_features.py      # 宏观经济特征
│   │   ├── postprocessing/
│   │   │   ├── conformal.py           # 保形预测置信区间
│   │   │   └── constraints.py         # 净值约束 + 特殊时期调整
│   │   ├── pipelines/
│   │   │   └── flexible_pipeline.py   # 两阶段位置估计
│   │   └── rules/
│   │       └── index_rule_engine.py  # 指数ETF规则引擎
│   └── db/
│       ├── database.py             # SQLite连接池（WAL+线程本地）
│       └── models.py               # ORM模型定义
├── frontend/src/
│   ├── api/                        # 6个API调用模块（对应后端）
│   ├── views/                      # 8个页面组件
│   ├── utils/logger.js             # 前端结构化日志
│   └── utils/request.js            # Axios拦截器（自动注入日志）
├── data/raw/                       # 原始CSV（基金净值/持仓/指数/个股）
├── data/processed/                 # 处理后的数据集
├── models/{fund_code}/             # 训练产物（model.pkl/metrics.json等）
├── logs/                           # 日志输出（6种文件）
└── tests/                          # 单元测试（36个用例）
```

### 模块依赖图

```
main.py
  ├─> routing_service.py
  │     └─> fund_profile_service.py  (三级分类)
  │           └─> data_service.py    (获取基础信息)
  ├─> prediction_service.py
  │     ├─> data_service.py          (Step 1: 数据获取)
  │     ├─> feature_service.py       (Step 2: 特征构建)
  │     │     ├─> enhanced_equity_features.py
  │     │     ├─> bond_features.py
  │     │     └─> macro_features.py
  │     ├─> factor_screening.py      (Step 3: 因子筛选)
  │     ├─> model_selection_service.py (Step 4: 训练+选择)
  │     │     └─> ensemble.py        (Stacking集成)
  │     ├─> conformal.py             (Step 5: 置信区间)
  │     └─> constraints.py           (Step 6: 净值约束)
  ├─> cold_start.py                 (历史<220天时启用)
  └─> intraday_service.py           (T日日内估计)
```

---

## 3. 数据获取详细流程

### 3.1 数据源总览

| 数据类型 | 来源 | 存储位置 | 更新频率 |
|---------|------|---------|---------|
| 基金净值 | AKShare API / 本地CSV | `data/raw/fund_nav/{code}.csv` | 每日收盘后 |
| 市场指数 | AKShare API / 本地CSV | `data/raw/index/{index}.csv` | 每日收盘后 |
| 基金持仓 | AKShare API / 本地CSV | `data/raw/holdings/{code}.csv` | 季报披露后 |
| 基金画像 | AKShare API / SQLite缓存 | `data/fund_profiles.db` | 首次获取后缓存 |
| 宏观经济 | AKShare API | 内存实时获取 | 按需获取 |

### 3.2 基金净值数据获取 (`data_service.fetch_fund_nav`)

```python
def fetch_fund_nav(fund_code: str, require_fresh: bool = False) -> tuple[pd.DataFrame, datetime]:
```

**输入参数**:
- `fund_code`: 6位基金代码 (如 "110011")
- `require_fresh`: 是否强制刷新缓存

**处理流程**:

```
输入: fund_code="110011", require_fresh=False
  │
  ├─ Step 1: 检查内存缓存 (_NAV_CACHE)
  │     线程安全: 使用 threading.RLock() 保护
  │     缓存键: fund_code
  │     缓存值: (DataFrame, cached_at)
  │     TTL: 1小时 (3600秒)
  │     
  │     IF cached 且 (now - cached_at) < 3600s:
  │         RETURN cached_df, cached_at
  │     ELSE:
  │         继续 Step 2
  │
  ├─ Step 2: 读取本地CSV文件
  │     路径: ROOT/data/raw/fund_nav/110011.csv
  │     文件格式:
  │         date, nav, daily_growth_pct
  │         2024-01-01, 1.2345, 0.0123
  │     
  │     IF 文件不存在:
  │         跳转到 Step 3 (API获取)
  │     
  │     读取CSV → DataFrame
  │     解析日期列 → datetime类型
  │     记录文件mtime → last_update_time
  │     
  │     更新 _DATA_FRESHNESS[fund_code] = mtime
  │
  ├─ Step 3: AKShare API获取 (当本地数据不存在或需要刷新时)
  │     调用: ak.fund_open_fund_info_em(fund_code)
  │     返回字段:
  │         - 净值日期
  │         - 单位净值
  │         - 日增长率
  │     
  │     处理:
  │         - 重命名列名适配内部格式
  │         - 按日期排序
  │         - 保存到本地CSV (持久化)
  │
  ├─ Step 4: 数据质量检查
  │     - 检查空值比例 (< 30%)
  │     - 检查日期连续性 (缺失天数 < 10%)
  │     - 检查异常值 (日收益率 > ±20% 标记警告)
  │
  ├─ Step 5: 更新内存缓存
  │     with _NAV_CACHE_LOCK:
  │         _NAV_CACHE[fund_code] = (df, datetime.now())
  │
  └─ 返回: (DataFrame, last_update_time)
```

**输出字段**:
| 字段名 | 类型 | 说明 |
|-------|------|------|
| date | datetime | 交易日日期 |
| nav | float | 单位净值 |
| daily_growth_pct | float | 日涨跌幅 (%) |

### 3.3 市场指数数据获取 (`data_service.load_market_data`)

```python
def load_market_data(require_fresh: bool = False) -> tuple[dict[str, pd.DataFrame], datetime]:
```

**获取的指数列表**:

| 指数代码 | 指数名称 | 用途 |
|---------|---------|------|
| hs300 | 沪深300 | 大盘基准、Beta计算、风格对比 |
| zz500 | 中证500 | 中盘基准、风格对比 |
| zz1000 | 中证1000 | 小盘基准、风格对比 |
| cyb | 创业板指 | 成长风格、风格对比 |
| kcb50 | 科创50 | 科技风格、风格对比 |
| sh000688 | 上证红利 | 价值风格 |
| sz399006 | 创业板R | 备用成长指标 |

**并发获取机制**:

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(fetch_index_data, index_code): index_code
        for index_code in INDEX_CODES
    }
    
    for future in as_completed(futures):
        index_code = futures[future]
        try:
            index_data[index_code] = future.result(timeout=20)
        except Exception as e:
            logger.warning(f"Index fetch failed: {index_code}, error: {e}")
            # Fallback to local CSV
            index_data[index_code] = load_index_from_csv(index_code)
```

**Fallback链**:
```
AKShare API (ak.index_zh_a_hist)
    ↓ 失败 (Timeout/ProxyError/503)
本地CSV (data/raw/index/{code}.csv)
    ↓ 失败 (文件不存在)
NaN填充 (该指数列全为空，后续特征计算会跳过)
```

**指数数据处理**:
```python
# 计算日收益率
df["ret"] = df["close"].pct_change()

# 重命名列避免冲突
df = df.rename(columns={"ret": f"{index_code}_ret"})

# 只保留必要列
df = df[["date", f"{index_code}_ret"]]
```

### 3.4 数据合并流程

```python
def merge_fund_with_indices(fund_df: pd.DataFrame, index_dict: dict) -> pd.DataFrame:
```

**合并逻辑**:

```
输入: fund_df (基金净值数据), index_dict (各指数数据字典)
  │
  ├─ 以 fund_df 为左表 (LEFT JOIN)
  │     确保基金数据不丢失，即使某些指数缺失
  │
  ├─ 对每个指数:
  │     fund_df = fund_df.merge(
  │         index_df[["date", f"{idx}_ret"]],
  │         on="date",
  │         how="left"
  │     )
  │
  ├─ 数据对齐检查
  │     - 检查合并后行数是否一致
  │     - 检查日期范围是否覆盖
  │     - 标记缺失的指数数据
  │
  └─ 返回: 合并后的DataFrame
      列: [date, nav, daily_growth_pct, hs300_ret, zz500_ret, zz1000_ret, cyb_ret, kcb50_ret, ...]
```

### 3.5 数据新鲜度检查

```python
def check_data_freshness(fund_code: str, stale_days: int = 3) -> str | None:
```

**检查逻辑**:
```
获取 last_update_time (CSV文件mtime)
计算 days_stale = (now - last_update_time).days

IF days_stale > stale_days:
    RETURN f"数据已滞后{days_stale}天(>{stale_days}天)"
ELSE:
    RETURN None
```

**在预测流程中的应用**:
```python
# prediction_service.py
warning = check_data_freshness(fund_code, stale_days=STALE_WARNING_DAYS)
if warning:
    result["data_warning"] = warning
```

---

## 4. 特征工程详细流程

### 4.1 特征工程总览

| 特征类别 | 数量 | 计算窗口 | 用途 |
|---------|------|---------|------|
| Lag特征 | 5 | [1,2,3,5,10] | 捕捉短期自相关 |
| Rolling统计 | 24 | [5,10,20,60] | 波动率、趋势强度 |
| Beta特征 | ≤5 | 20日 | 系统性风险暴露 |
| 回撤特征 | 4 | [20,60] | 下行风险 |
| 动量特征 | 3 | [5,20,60] | 趋势延续性 |
| 波动率比 | ≤2 | [20,60] | 相对波动水平 |
| 风格暴露 | ≤6 | 60日 | 风格因子暴露 |
| 增强特征 | ~15 | - | 市场情绪、日历效应 |
| 债券特征 | ~8 | - | 久期、利率敏感度 |
| 宏观特征 | ~5 | - | 经济周期指标 |
| **总计** | **~80** | - | - |

### 4.2 特征构建主流程 (`feature_service.build_features`)

```python
def build_features(fund_code: str, df: pd.DataFrame, fund_type: str) -> pd.DataFrame:
```

**输入**:
- `fund_code`: 基金代码
- `df`: 合并后的原始数据 (含基金净值+指数收益率)
- `fund_type`: 基金类型 (决定加载哪些增强特征)

**输出**:
- 特征矩阵 DataFrame (~80列)

### 4.3 各类特征详细计算

#### 4.3.1 Lag特征 (时滞特征)

```python
# 配置参数
LOOKBACK_LAGS = [1, 2, 3, 5, 10]

for lag in LOOKBACK_LAGS:
    df[f"fund_ret_lag{lag}"] = df["daily_growth_pct"].shift(lag)
```

**计算示例**:
```
date       daily_growth_pct    fund_ret_lag1    fund_ret_lag2
2024-01-05      0.5%              NaN              NaN
2024-01-08      1.2%             0.5%              NaN
2024-01-09     -0.3%             1.2%             0.5%
2024-01-10      0.8%            -0.3%             1.2%
```

#### 4.3.2 Rolling统计特征

```python
# 配置参数
ROLLING_WINDOWS = [5, 10, 20, 60]

for w in ROLLING_WINDOWS:
    # 均值 - 趋势强度
    df[f"fund_ret_mean_{w}"] = df["daily_growth_pct"].rolling(w).mean()
    
    # 标准差 - 波动率
    df[f"fund_ret_std_{w}"] = df["daily_growth_pct"].rolling(w).std()
    
    # 最大值/最小值 - 极端收益
    df[f"fund_ret_max_{w}"] = df["daily_growth_pct"].rolling(w).max()
    df[f"fund_ret_min_{w}"] = df["daily_growth_pct"].rolling(w).min()
    
    # 偏度 - 收益分布不对称性
    df[f"fund_ret_skew_{w}"] = df["daily_growth_pct"].rolling(w).skew()
    
    # 峰度 - 收益分布尾部厚度
    df[f"fund_ret_kurt_{w}"] = df["daily_growth_pct"].rolling(w).kurt()
```

#### 4.3.3 Beta特征 (系统性风险)

```python
# 配置参数
BETA_WINDOW = 20
INDEX_LIST = ["hs300", "zz500", "zz1000", "cyb", "kcb50"]

for idx in INDEX_LIST:
    col_name = f"{idx}_ret"
    if col_name not in df.columns:
        continue  # 跳过不存在的指数
    
    # 滚动窗口计算Beta
    def calc_beta(x):
        if len(x) < BETA_WINDOW:
            return np.nan
        fund_ret = x["daily_growth_pct"].values
        idx_ret = x[col_name].values
        
        # Beta = Cov(fund, index) / Var(index)
        cov = np.cov(fund_ret, idx_ret)[0, 1]
        var = np.var(idx_ret)
        
        return cov / var if var > 0 else np.nan
    
    df[f"beta_{idx}"] = df.rolling(BETA_WINDOW).apply(calc_beta, raw=False)
```

#### 4.3.4 回撤特征 (下行风险)

```python
# 计算滚动最大值 (前N日最高净值)
df["rolling_max_20"] = df["nav"].rolling(20).max()
df["rolling_max_60"] = df["nav"].rolling(60).max()

# 回撤 = (当前净值 - 前N日最高) / 前N日最高
df["drawdown_20d"] = (df["nav"] - df["rolling_max_20"]) / df["rolling_max_20"]
df["drawdown_60d"] = (df["nav"] - df["rolling_max_60"]) / df["rolling_max_60"]

# 最大回撤 (过去N日内的最大回撤值)
df["max_drawdown_20d"] = df["drawdown_20d"].rolling(20).min()
df["max_drawdown_60d"] = df["drawdown_60d"].rolling(60).min()
```

#### 4.3.5 动量特征 (趋势延续)

```python
MOMENTUM_PERIODS = [5, 20, 60]

for period in MOMENTUM_PERIODS:
    # 动量 = (当前净值 / N日前净值) - 1
    df[f"mom_{period}d"] = df["nav"] / df["nav"].shift(period) - 1
```

#### 4.3.6 波动率比 (相对波动)

```python
VOL_WINDOWS = [20, 60]

for w in VOL_WINDOWS:
    fund_vol = df["daily_growth_pct"].rolling(w).std()
    
    if "hs300_ret" in df.columns:
        idx_vol = df["hs300_ret"].rolling(w).std()
        df[f"vol_ratio_{w}d"] = fund_vol / (idx_vol + 1e-8)  # 避免除零
```

#### 4.3.7 风格暴露特征

```python
STYLE_WINDOW = 60

# 成长 vs 大盘 (创业板 - 沪深300)
if "cyb_ret" in df.columns and "hs300_ret" in df.columns:
    df["style_growth_vs_large"] = df["cyb_ret"] - df["hs300_ret"]
    df["style_growth_vs_large_mean_5"] = df["style_growth_vs_large"].rolling(5).mean()
    df["style_growth_vs_large_mean_20"] = df["style_growth_vs_large"].rolling(20).mean()

# 小盘 vs 大盘 (中证1000 - 沪深300)
if "zz1000_ret" in df.columns and "hs300_ret" in df.columns:
    df["style_small_vs_large"] = df["zz1000_ret"] - df["hs300_ret"]
    df["style_small_vs_large_mean_5"] = df["style_small_vs_large"].rolling(5).mean()
    df["style_small_vs_large_mean_20"] = df["style_small_vs_large"].rolling(20).mean()

# 科技 vs 大盘 (科创50 - 沪深300)
if "kcb50_ret" in df.columns and "hs300_ret" in df.columns:
    df["style_tech_vs_large"] = df["kcb50_ret"] - df["hs300_ret"]
    df["style_tech_vs_large_mean_5"] = df["style_tech_vs_large"].rolling(5).mean()
    df["style_tech_vs_large_mean_20"] = df["style_tech_vs_large"].rolling(20).mean()
```

### 4.4 目标变量构建

```python
# T+1 日收益率作为预测目标
df["target_next"] = df["daily_growth_pct"].shift(-1)
```

**注意**: `shift(-1)` 表示向前移动，即用当日特征预测次日收益。最后一行会是NaN（无次日数据），在训练时会剔除。

### 4.5 增强特征（按基金类型加载）

#### 4.5.1 股票类基金增强特征

```python
# enhanced_equity_features.py

def build(df: pd.DataFrame) -> pd.DataFrame:
    """市场情绪 + 日历效应 + 动量质量"""
    
    # 市场情绪指标
    df["market_breadth"] = df["advance_count"] / (df["decline_count"] + 1e-8)
    df["new_high_low_ratio"] = df["new_high"] / (df["new_low"] + 1e-8)
    df["volume_ma_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    
    # 日历效应
    df["is_month_start"] = (df["date"].dt.day <= 5).astype(int)
    df["is_month_end"] = (df["date"].dt.day >= 25).astype(int)
    df["is_monday"] = (df["date"].dt.dayofweek == 0).astype(int)
    df["is_friday"] = (df["date"].dt.dayofweek == 4).astype(int)
    
    # 动量质量
    up_vol = df[df["daily_growth_pct"] > 0]["daily_growth_pct"].rolling(20).std()
    down_vol = df[df["daily_growth_pct"] < 0]["daily_growth_pct"].rolling(20).std()
    df["up_down_vol_ratio"] = up_vol / (down_vol + 1e-8)
    
    return df
```

#### 4.5.2 债券类基金特征

```python
# bond_features.py

def build(df: pd.DataFrame, duration: float = 2.5) -> pd.DataFrame:
    """债券物理先验 + 利率曲线 + 信用利差"""
    
    # 物理先验: -duration × Δy
    # 利率变动对净值的直接影响
    if "bond_yield_change" in df.columns:
        df["bond_physics_prior"] = -duration * df["bond_yield_change"]
    
    # 期限结构斜率 (长端 - 短端)
    if "yield_10y" in df.columns and "yield_1y" in df.columns:
        df["yield_curve_slope"] = df["yield_10y"] - df["yield_1y"]
    
    # 信用利差 (企业债 - 国债)
    if "corp_bond_yield" in df.columns and "gov_bond_yield" in df.columns:
        df["credit_spread"] = df["corp_bond_yield"] - df["gov_bond_yield"]
    
    return df
```

#### 4.5.3 宏观特征

```python
# macro_features.py

def build(df: pd.DataFrame) -> pd.DataFrame:
    """宏观经济指标"""
    
    # 债券收益率变化
    df["bond_yield_change_5d"] = df["bond_yield"].diff(5)
    
    # CPI/PPI相关
    df["cpi_yoy_change"] = df["cpi"].pct_change(252)  # 同比变化
    
    # PMI
    df["pmi_ma3"] = df["pmi"].rolling(3).mean()
    
    # 北向资金流向
    df["north_flow_ma5"] = df["north_flow"].rolling(5).mean()
    
    # 银行间利率 (DR007)
    df["dr007_change"] = df["dr007"].diff()
    
    return df
```

### 4.6 特征工程输出

**最终特征矩阵示例**:

| 字段名 | 示例值 | 说明 |
|-------|--------|------|
| date | 2024-01-10 | 日期 |
| fund_ret_lag1 | 0.012 | 昨日收益率 |
| fund_ret_mean_20 | 0.008 | 20日均值 |
| fund_ret_std_20 | 0.015 | 20日波动率 |
| beta_hs300 | 0.85 | 沪深300 Beta |
| drawdown_20d | -0.03 | 20日回撤 |
| mom_20d | 0.05 | 20日动量 |
| style_growth_vs_large | 0.02 | 成长风格暴露 |
| target_next | 0.006 | T+1目标 (预测对象) |

---

## 5. 基金分类路由系统

### 5.1 三级分类逻辑 (`fund_profile_service.py`)

```python
def classify_fund(fund_code: str) -> FundProfile:
```

**Level 1 — Benchmark 权重智能解析** (最优先):

```python
def _parse_benchmark_weight(benchmark: str) -> float | None:
    """解析基准字符串中的股票权重"""
    # 支持格式: "沪深300×80%+中证全债×20%" → 0.80
    # 支持格式: "50%+50%" → 0.50
    
    patterns = [
        r'(\d+(?:\.\d+)?)\s*[%％]',      # "80%" or "80％"
        r'[\*×]\s*(\d+(?:\.\d+)?)',      # "*80" or "×80"
    ]
    
    weights = []
    for pattern in patterns:
        matches = re.findall(pattern, benchmark)
        for m in matches:
            w = float(m) / 100.0
            if 0.0 <= w <= 1.0:
                weights.append(w)
    
    return max(weights) if weights else None
```

**分类规则**:

| 股票权重 | fund_type |
|---------|-----------|
| > 0.65 | `hybrid_equity` (偏股) |
| 0.40 - 0.65 | `hybrid_balanced` (均衡) |
| < 0.40 | `hybrid_bond` (偏债) |

**Level 2 — 名称关键词推断** (无benchmark时):

| name 关键字 | fund_type |
|---|---|
| 成长 / 科技 / 医药 / 消费 / 新能源 | `equity_active` |
| 价值 / 红利 / 低波 / 增强 | `equity_active` |
| 债券 / 信用 / 利率 | `bond_pure` |
| 可转 | `bond_convertible` |
| 灵活配置 / 精选 | `hybrid_flexible` |
| FOF / 养老 | `fof` |
| QDII / 港股 / 海外 | `qdii` |
| 指数 / ETF / LOF | `index_equity` |

**Level 3 — 默认**: `hybrid_equity`

**货币基金强制约束**:
```python
# 无论走哪条路径，货币基金都强制skip
if profile.fund_type == "money_market":
    profile.skip_prediction = True
```

### 5.2 路由决策树 (`routing_service.py`)

```
输入: FundProfile
  │
  ├─ skip_prediction == True?
  │   └─→ 返回 "货币基金无需预测" 或 "净值恒为1"
  │
  ├─ fund_type == "index_equity"?
  │   └─→ index_rule_engine.predict_index_fund()
  │       (规则: pred = index_ret × (1 - daily_fee))
  │
  ├─ fund_type in ("hybrid_equity", "equity_active")?
  │   └─→ prediction_service.predict_next() (成熟ML流水线)
  │
  └─ 其他 (bond/fof/qdii/hybrid_*)?
      └─→ prediction_service.predict_next() (通用ML流程)
```

---

## 6. 因子预筛选

### 6.1 四轮筛选流程

```
输入: ~80 个候选特征
  │
  ▼
Round 1: IC 检验 (Spearman RankIC, 阈值: |IC| ≥ 0.02)
  保留: 与目标相关性显著的特征
  白名单豁免: fund_ret_lag1, fund_ret_lag2, hs300_ret, zz500_ret
  ↓ (~移除 10-20 个弱相关特征)
  ▼
Round 2: 相关性聚类去重 (|corr| > 0.80)
  方法: 计算Spearman相关系数矩阵
        |corr| > 0.80 的特征归为一个簇
        每簇保留 |IC| 最大的特征
  ↓ (~移除 5-15 个冗余特征)
  ▼
Round 3: ICIR 稳定性检验 (阈值: ICIR ≥ 0.5)
  ICIR = mean(rolling_IC) / std(rolling_IC)
  含义: 因子的预测能力是否稳定
  ↓ (~移除 5-10 个不稳定特征)
  ▼
Round 4: 衰减测试 (仅top20)
  验证因子的信息是否随时间快速衰减
  输出: 最佳滞后期, 衰减速率
  ↓ (仅记录, 不做硬性排除)
  ▼
输出: screened_features (~30-50 个)
```

### 6.2 IC 计算 (Spearman RankIC)

```python
from scipy import stats

# 计算Spearman秩相关系数 (对异常值鲁棒)
spearman_rho, p_value = stats.spearmanr(x, y)

# 保留Pearson作为参考
pearson_r, _ = stats.pearsonr(x, y)

ic_results[col] = {
    "ic_spearman": float(spearman_rho),      # 主筛选依据
    "ic_pearson": float(pearson_r),          # 参考信息
    "abs_ic_spearman": abs(float(spearman_rho)),
}
```

### 6.3 相关性聚类去重

```python
def _cluster_dedup_features(df, features, ic_results, corr_threshold=0.80):
    """基于相关性的聚类去重"""
    
    # 计算Spearman相关系数矩阵
    corr_matrix = df[features].corr(method="spearman").abs()
    
    assigned = set()
    clusters = []
    
    # 构建聚类
    for i, col_i in enumerate(features):
        if col_i in assigned:
            continue
        cluster = [col_i]
        assigned.add(col_i)
        
        for j, col_j in enumerate(features):
            if i >= j or col_j in assigned:
                continue
            if corr_matrix.loc[col_i, col_j] > corr_threshold:
                cluster.append(col_j)
                assigned.add(col_j)
        
        clusters.append(cluster)
    
    # 每簇保留IC最大的
    kept = []
    removed = []
    for cluster in clusters:
        if len(cluster) == 1:
            kept.append(cluster[0])
        else:
            best = max(cluster, key=lambda c: abs(ic_results[c]["ic_spearman"]))
            kept.append(best)
            removed.extend([c for c in cluster if c != best])
    
    return kept, removed
```

---

## 7. 模型训练与选择

### 7.1 四段数据划分

```
时间轴 ─────────────────────────────────────────────►
       |--------Train 55%-------|--Valid 22%--|-Test_sel 13%|-Test_fin 10%|
       0                      T*0.55         T*0.77       T*0.90        T*1.0
       
用途:
- Train (55%): 模型参数拟合
- Valid (22%): 模型选择、Stacking元学习器训练
- Test_sel (13%): 保形预测校准集 (严格隔离!)
- Test_fin (10%): 最终泛化评估 (严格隔离!)
```

**代码实现**:
```python
def _split_train_valid_test(df):
    n = len(df)
    train_end = int(n * 0.55)
    valid_end = train_end + int(n * 0.22)
    test_sel_end = valid_end + int(n * 0.13)
    
    X_train = df.iloc[:train_end].copy()           # 模型训练
    X_valid = df.iloc[train_end:valid_end].copy()  # 模型选择
    X_calib = df.iloc[valid_end:test_sel_end].copy()  # 保形校准
    X_final = df.iloc[test_sel_end:].copy()        # 最终评估
    
    return X_train, X_valid, X_calib, X_final
```

### 7.2 Walk-Forward CV (动态参数)

```python
def walk_forward_cv(df, model, train_months=24, valid_months=3, step_months=1):
    """Walk-Forward交叉验证"""
    
    T = len(df)
    
    # 动态调整窗口大小
    dyn_train = min(500, int(T * 0.55))   # 约24个月
    dyn_valid = min(60, int(T * 0.22))    # 约3个月
    
    results = []
    n_rounds = 0
    
    for offset in range(dyn_train, T - dyn_valid, dyn_valid // 3):
        X_train = df.iloc[offset - dyn_train:offset]
        X_valid = df.iloc[offset:offset + dyn_valid]
        
        # 样本时间权重 (半衰期60天)
        sample_weights = np.exp(-np.log(2) * np.arange(len(X_train)) / 60)
        
        model.fit(X_train[features], X_train[target], sample_weight=sample_weights)
        pred = model.predict(X_valid[features])
        
        # 记录指标
        mae = np.mean(np.abs(pred - X_valid[target]))
        direction_acc = np.mean(np.sign(pred) == np.sign(X_valid[target]))
        
        results.append({"mae": mae, "direction_accuracy": direction_acc})
        n_rounds += 1
    
    # 轮数不足3轮时降级为Hold-out
    if n_rounds < 3:
        return holdout_validation(df, model)
    
    return aggregate_results(results)
```

### 7.3 模型选择 (联合MAE+方向准确率)

```python
def select_best_model(cv_results):
    """选择最佳模型"""
    
    # 计算排名
    mae_ranks = {name: rank for rank, (name, _) in enumerate(
        sorted(cv_results.items(), key=lambda x: x[1]["mae"])
    )}
    
    da_ranks = {name: rank for rank, (name, _) in enumerate(
        sorted(cv_results.items(), key=lambda x: x[1]["direction_accuracy"], reverse=True)
    )}
    
    def selection_score(name):
        # 联合得分: 0.6*MAE排名 + 0.4*(1-DA排名)
        mae_norm = mae_ranks[name] / max(len(mae_ranks)-1, 1)
        da_norm = da_ranks[name] / max(len(da_ranks)-1, 1)
        return 0.6 * mae_norm + 0.4 * (1 - da_norm)
    
    # 排除方向准确率<52%的模型
    candidates = {
        name: res for name, res in cv_results.items()
        if res["direction_accuracy"] >= 0.52
    }
    
    if not candidates:
        candidates = cv_results  # 如果全部<52%，则全部纳入
    
    best_name = min(candidates.keys(), key=selection_score)
    return best_name, candidates[best_name]
```

---

## 8. 集成学习（Stacking）

### 8.1 两层架构

```
Layer 1: Base Models (并行训练)
┌─────────────┬──────────────┬─────────────┬──────────────┐
│   Ridge     │  ElasticNet  │    LGBM     │   XGBoost    │
│ (alpha=1.0) │ (alpha=0.01) │  (n=120)    │   (n=120)    │
└──────┬──────┴──────┬───────┴──────┬──────┴──────┬───────┘
       │             │              │             │
       ▼             ▼              ▼             ▼
   meta_feature[0]  meta_feature[1]  meta_feature[2]  meta_feature[3]
       │             │              │             │
       └─────────────┴──────────────┴─────────────┘
                            │
                            ▼
Layer 2: Meta Learner (Ridge Regression)
┌──────────────────────────────────────────────────┐
│  final_pred = w0 + w1·pred_ridge + w2·pred_enet  │
│              + w3·pred_lgbm + w4·pred_xgb        │
│                                                  │
│  权重: coef_ 反映各模型贡献度                     │
└──────────────────────────────────────────────────┘
```

### 8.2 Out-of-Fold预测

```python
class StackingEnsemble:
    def fit(self, X, y, base_models, meta_learner):
        # 生成元特征 (Out-of-Fold)
        meta_features = np.zeros((len(X), len(base_models)))
        
        kf = KFold(n_splits=5, shuffle=False)  # 时间序列不分shuffle
        for train_idx, valid_idx in kf.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[valid_idx]
            y_tr = y.iloc[train_idx]
            
            for i, (name, model) in enumerate(base_models.items()):
                model.fit(X_tr, y_tr)
                meta_features[valid_idx, i] = model.predict(X_val)
        
        # 训练元学习器
        self.meta_learner.fit(meta_features, y)
        self.base_models = base_models
    
    def predict(self, X):
        # 生成元特征
        meta_features = np.column_stack([
            model.predict(X) for model in self.base_models.values()
        ])
        # 元学习器预测
        return self.meta_learner.predict(meta_features)
```

---

## 9. 后处理：保形预测与净值约束

### 9.1 保形预测算法

```python
def conformal_interval(model, X_calib, y_calib, X_new, alpha=0.10):
    """保形预测：生成 coverage 保证的预测区间
    
    ⚠️ X_calib 必须为 Test_select(13%)段，不得复用 Valid 段!
    """
    
    # 前置判断
    if len(X_calib) < 20:
        # Fallback: 固定宽度区间
        pred = model.predict(X_new)
        half_width = np.abs(pred) * 0.02  # ±2%
        return pred - half_width, pred + half_width, {"method": "fallback"}
    
    # 计算非一致性得分
    calib_pred = model.predict(X_calib)
    scores = np.abs(y_calib - calib_pred)
    
    # 计算阈值 (90th percentile for alpha=0.10)
    threshold = np.quantile(scores, 1 - alpha)
    
    # 构建预测区间
    new_pred = model.predict(X_new)
    lower = new_pred - threshold
    upper = new_pred + threshold
    
    logger.info(
        "conformal_prediction calib_size=%d alpha=%.2f threshold=%.4f",
        len(X_calib), alpha, threshold
    )
    
    return lower, upper, {
        "method": "conformal_quantile",
        "threshold": threshold,
        "coverage_target": 1 - alpha,
    }
```

### 9.2 净值约束

```python
NAV_LIMITS = {
    "hybrid_equity": 0.20,      # ±20%
    "equity_active": 0.20,      # ±20%
    "hybrid_balanced": 0.15,    # ±15%
    "hybrid_bond": 0.10,        # ±10%
    "bond_pure": 0.05,          # ±5%
    "bond_mixed": 0.08,         # ±8%
    "bond_convertible": 0.20,   # ±20%
    "index_equity": None,       # 不约束
    "fof": 0.15,                # ±15%
    "qdii": 0.20,               # ±20%
}

def apply_nav_constraints(pred_return, fund_type):
    limit = NAV_LIMITS.get(fund_type)
    
    if limit is None:
        return pred_return, False  # 不约束
    
    if pred_return < -limit:
        return -limit, True  # 触发下限
    elif pred_return > limit:
        return limit, True   # 触发上限
    else:
        return pred_return, False
```

### 9.3 特殊时期置信度调整

```python
def adjust_confidence_for_special_periods(date, fund_profile):
    penalties = []
    
    # 季报窗口 (3/6/9/12月 18-31日)
    if date.month in [3, 6, 9, 12] and date.day >= 18:
        penalties.append(-0.15)
    
    # 月末效应 (≥28日)
    if date.day >= 28:
        penalties.append(-0.05)
    
    # 年末效应 (12月 ≥20日)
    if date.month == 12 and date.day >= 20:
        penalties.append(-0.10)
    
    # 经理变更 (<90天)
    if fund_profile.manager_tenure_days < 90:
        penalties.append(-0.25)
    
    total_penalty = max(sum(penalties), -0.40)  # 上限-40%
    return total_penalty
```

---

## 10. 冷启动机制

### 10.1 触发条件

```python
def should_use_group_model(fund_code, history_days):
    """判断是否使用群体模型"""
    
    # 0-219天: 使用群体模型 (100%)
    if history_days < 220:
        return True, history_days
    
    # 220-400天: 渐变过渡
    if history_days < 400:
        return True, history_days
    
    # 400天以上: 使用个体模型
    return False, history_days
```

### 10.2 群体模型算法

```python
def get_group_model_prediction(fund_code, fund_type, features):
    """群体模型预测"""
    
    # 1. 找同类型同伴
    peers = find_peers_by_type(fund_type, exclude=fund_code)
    
    # 2. 同伴推理
    peer_predictions = []
    for peer in peers:
        model = load_model(peer)
        pred = model.predict(features[model.selected_features])
        peer_predictions.append(pred)
    
    # 3. 基线聚合
    baseline = np.mean(peer_predictions)
    
    # 4. 微调修正
    history_days = get_history_days(fund_code)
    blend_weight = min(1.0, (history_days - 220) / (400 - 220)) if history_days >= 220 else 0
    
    recent_mean = get_recent_return(fund_code, days=30)
    adjustment = recent_mean * (1 - blend_weight) * 0.5
    
    # 5. 最终融合
    final = baseline * (1 - blend_weight * 0.5) + adjustment
    
    return final
```

---

## 11. API 接口规范

### 11.1 核心接口

| 方法 | 路径 | 功能 |
|-----|------|------|
| POST | `/api/v1/fund/predict` | 基金预测 |
| GET | `/api/v1/fund/{code}/profile` | 基金画像 |
| POST | `/api/v1/train` | 创建训练任务 |
| GET | `/api/v1/tasks/{id}` | 任务状态 |

### 11.2 预测请求/响应

**请求**:
```json
{
  "fund_code": "110011",
  "prediction_mode": "t_plus_1_close"
}
```

**响应**:
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "fund_type": "equity_active",
    "predicted_return": 0.0035,
    "confidence_interval": [-0.0082, 0.0152],
    "direction": "up",
    "direction_probability": 0.62,
    "confidence_level": 0.90,
    "model_info": {
      "model_type": "ridge",
      "mae": 0.012,
      "direction_accuracy": 0.58,
      "features_used": 38
    },
    "data_warning": null,
    "fund_profile": {
      "type": "equity_active",
      "name": "易方达中小盘混合"
    }
  }
}
```

---

## 12. 配置参数手册

### 12.1 核心配置 (config.yaml)

```yaml
# 数据获取
data:
  cache_stale_days: 10
  min_train_rows: 220
  fetch_timeout_seconds: 20
  fetch_max_workers: 5
  stale_warning_days: 3

# 特征工程
feature:
  lookback_lags: [1, 2, 3, 5, 10]
  rolling_windows: [5, 10, 20, 60]
  beta_window: 20
  style_window: 60

# 因子筛选
screening:
  ic_threshold: 0.02
  vif_threshold: 10.0
  icir_threshold: 0.5
  corr_cluster_threshold: 0.80

# 模型训练
model:
  train_split_ratio: [0.55, 0.22, 0.13, 0.10]
  sample_weight_halflife: 60
  walk_forward_min_rounds: 3
  direction_accuracy_threshold: 0.52
  
  # GPU加速配置 (v2.6+)
  use_gpu: false                    # 是否启用GPU加速
  gpu_device: "cuda:0"              # GPU设备 (cuda:0 / cuda:1 / cpu)
  gpu_min_samples: 10000            # 最小样本数才启用GPU (小数据集CPU更快)

# 冷启动
cold_start:
  group_model_days: 250
  individual_model_days: 400
```

### 12.2 GPU加速说明 (v2.6+)

**支持的模型**:
| 模型 | GPU支持 | 说明 |
|------|---------|------|
| XGBoost | ✅ | `tree_method="hist"` + `device="cuda"` |
| LightGBM | ✅ | `device="cuda"` |
| Ridge/ElasticNet | ❌ | scikit-learn仅CPU |
| RandomForest | ❌ | scikit-learn仅CPU |

**启用GPU的条件**:
```python
# 必须同时满足:
1. config.yaml 中 use_gpu: true
2. 训练样本数 >= gpu_min_samples (默认10000)
3. 系统已安装CUDA和对应库:
   - xgboost>=2.0 (带CUDA支持)
   - lightgbm>=4.0 (带CUDA支持)
```

**自动降级机制**:
```
IF use_gpu=false OR n_samples < gpu_min_samples:
    device = "cpu"  # 强制使用CPU
ELSE IF CUDA不可用:
    device = "cpu"  # 自动降级到CPU
    记录警告日志
ELSE:
    device = config.gpu_device  # 使用GPU
```

**性能建议**:
- 小数据集 (<10000样本): CPU更快 (GPU初始化开销)
- 大数据集 (>50000样本): GPU显著加速 (5-10x)
- 基金数据通常样本数较少，建议保持 `use_gpu: false`

---

## 13. 前端架构

### 13.1 技术栈

- Vue 3 + Vite
- Element Plus (UI组件)
- ECharts 5 (图表)
- Axios (HTTP)
- Pinia (状态管理)

### 13.2 页面路由

| 路径 | 组件 | 功能 |
|------|------|------|
| `/` | Dashboard | 总览仪表盘 |
| `/predict` | Predict | 单基金预测 |
| `/train` | Train | 模型训练 |
| `/backtest` | Backtest | 历史回测 |

---

## 14. 日志系统

### 14.1 日志文件

| 文件 | 格式 | 用途 |
|------|------|------|
| `logs/app.log` | 文本 | 应用主日志 |
| `logs/api.jsonl` | JSONL | API访问日志 |
| `logs/train.log` | 文本 | 训练过程 |
| `logs/error.log` | 文本 | 错误日志 |
| `logs/audit.jsonl` | JSONL | 审计日志 |
| `logs/perf.jsonl` | JSONL | 性能指标 |

---

## 15. 端到端完整数据流

```
用户发起预测请求
  │
  ├─ ① API接收 (fund.py)
  │     └─ 生成 request_id, 记录日志
  │
  ├─ ② 基金分类 (fund_profile_service.classify_fund)
  │     ├─ Level 1: Benchmark权重解析
  │     ├─ Level 2: 名称关键词推断
  │     └─ Level 3: 默认hybrid_equity
  │
  ├─ ③ 路由决策 (routing_service.route_predict)
  │     ├─ skip? → 返回提示
  │     ├─ index_equity? → 规则引擎
  │     └─ 其他 → ML流程
  │
  ├─ ④ 数据获取 (data_service)
  │     ├─ 内存缓存检查 (RLock保护)
  │     ├─ 本地CSV读取
  │     ├─ AKShare API获取 (并发5线程)
  │     ├─ Fallback链处理
  │     └─ 数据新鲜度检查
  │
  ├─ ⑤ 特征构建 (feature_service.build_features)
  │     ├─ Lag特征 (5个)
  │     ├─ Rolling统计 (24个)
  │     ├─ Beta特征 (≤5个)
  │     ├─ 回撤/动量/波动率比
  │     ├─ 风格暴露 (≤6个)
  │     ├─ 增强特征 (按类型加载)
  │     └─ 目标变量 (T+1收益)
  │
  ├─ ⑥ 因子筛选 (factor_screening)
  │     ├─ Round 1: IC检验 (Spearman)
  │     ├─ Round 2: 聚类去重 (|corr|>0.80)
  │     ├─ Round 3: ICIR稳定性
  │     └─ Round 4: 衰减测试
  │
  ├─ ⑦ 模型训练 (model_selection_service)
  │     ├─ 四段划分 (55/22/13/10)
  │     ├─ Walk-Forward CV (动态参数)
  │     ├─ 方向准确率计算
  │     ├─ 联合得分选模 (0.6MAE+0.4DA)
  │     ├─ Stacking集成
  │     └─ 残差自适应修正
  │
  ├─ ⑧ 保形预测 (conformal)
  │     ├─ 使用Test_sel(13%)校准
  │     ├─ 计算90th percentile阈值
  │     └─ 构建预测区间
  │
  ├─ ⑨ 净值约束 (constraints)
  │     ├─ 按类型查表限制
  │     ├─ 触发裁剪时降级置信度
  │     └─ 特殊时期罚分调整
  │
  └─ ⑩ 返回结果
        ├─ 预测值 + 置信区间
        ├─ 方向概率
        ├─ 模型信息
        ├─ 数据警告(如有)
        └─ 基金画像
```

---

*文档结束 | 版本 v2.6.0 | 基于 system_review_and_improvements.md 修复后更新*
