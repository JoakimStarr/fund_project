# 基金净值预测系统 · 完整前后端实现方案

> 版本：v1.0 | 技术栈：FastAPI + Vue3 + AKShare + GLM/SiliconFlow
> 本文档涵盖完整的项目结构、数据库设计、所有 API、前后端实现细节，可直接按此开发。

---

## 目录

1. [项目概述与技术选型](#1-项目概述与技术选型)
2. [完整文件结构](#2-完整文件结构)
3. [数据库设计](#3-数据库设计)
4. [AKShare 接口清单](#4-akshare-接口清单)
5. [后端 API 完整设计](#5-后端-api-完整设计)
6. [后端服务层详细设计](#6-后端服务层详细设计)
7. [前端页面详细设计](#7-前端页面详细设计)
8. [前端组件详细设计](#8-前端组件详细设计)
9. [配置文件](#9-配置文件)
10. [启动与部署](#10-启动与部署)

---

## 1. 项目概述与技术选型

### 1.1 系统功能边界

| 功能模块 | 说明 |
|---|---|
| T+1 净值预测 | 收盘后预测下一交易日基金净值涨跌幅及置信区间 |
| T 日盘中估算 | 交易时段内基于持仓映射实时估算当日净值 |
| 模型训练 | 为指定基金训练专属预测模型（异步任务） |
| 回测诊断 | 查看历史预测的准确率、MAE、方向命中率 |
| 基金画像 | 展示基金基本信息、类型、持仓、风险特征 |
| 多基金对比 | 同时展示多只基金的预测结果和对比图表 |
| AI 解读 | 调用 GLM/SiliconFlow 生成自然语言分析报告 |
| 新闻聚合 | 通过 AKShare 聚合财联社、东方财富等财经新闻 |
| 数据管理 | 管理员查看数据新鲜度、手动触发更新 |

### 1.2 技术选型

| 层 | 选型 | 版本 | 选择理由 |
|---|---|---|---|
| 后端框架 | FastAPI | 0.115+ | 异步原生、自动文档、类型安全 |
| ASGI 服务器 | Uvicorn | 0.30+ | FastAPI 标配 |
| 数据库 | SQLite（WAL模式） | 内置 | 零依赖部署，WAL 支持并发读 |
| ORM | SQLAlchemy | 2.0+ | async 支持 |
| 数据获取 | AKShare | 最新 | 雪球/新浪/东方财富全覆盖，免费 |
| HTTP 客户端 | httpx | 0.27+ | 异步，兼容 OpenAI 格式 |
| 机器学习 | scikit-learn + lightgbm | 最新 | 模型训练核心 |
| 任务调度 | APScheduler | 3.10+ | 每日数据更新定时任务 |
| 前端框架 | Vue 3（Composition API） | 3.4+ | 现代前端标配 |
| 构建工具 | Vite | 5.x | 极速热更新 |
| UI 组件库 | Element Plus | 2.x | 中文生态完善 |
| 图表 | ECharts | 5.x | 金融图表丰富 |
| HTTP | Axios | 1.x | 拦截器完善 |
| 状态管理 | Pinia | 2.x | Vue3 官方推荐 |
| AI Provider | 智谱 GLM + 硅基流动 | — | OpenAI 兼容，中文优秀 |

---

## 2. 完整文件结构

```
fund_predictor/
│
├── .env                           # 环境变量（不提交 git）
├── .env.example                   # 环境变量模板（提交 git）
├── .gitignore
├── config.yaml                    # 全局配置
├── docker-compose.yml             # 容器编排
├── requirements.txt               # Python 依赖
│
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 应用入口
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py          # 配置加载器（读 config.yaml + .env）
│   │   │   ├── database.py        # SQLite 连接池（WAL + 线程本地）
│   │   │   ├── errors.py          # 统一异常体系
│   │   │   ├── logging_config.py  # 结构化日志（6 个 Handler）
│   │   │   ├── middleware.py      # 请求上下文、CORS、计时中间件
│   │   │   └── scheduler.py      # APScheduler 定时任务注册
│   │   │
│   │   ├── api/                   # 路由层（薄层，只做参数校验+调用 service）
│   │   │   ├── __init__.py
│   │   │   ├── router.py          # 汇总所有路由 include_router
│   │   │   ├── fund.py            # /fund 相关接口
│   │   │   ├── train.py           # /train 接口
│   │   │   ├── task.py            # /tasks 接口
│   │   │   ├── backtest.py        # /backtest 接口
│   │   │   ├── intraday.py        # /intraday 接口
│   │   │   ├── ai_analysis.py     # /ai 相关接口
│   │   │   ├── dashboard.py       # /dashboard 接口
│   │   │   └── admin.py           # /admin 接口
│   │   │
│   │   ├── schemas/               # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── fund.py
│   │   │   ├── train.py
│   │   │   ├── predict.py
│   │   │   ├── intraday.py
│   │   │   ├── ai_analysis.py
│   │   │   └── common.py          # 通用响应包装 ApiResponse[T]
│   │   │
│   │   ├── models/                # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── fund_nav.py        # 基金净值历史表
│   │   │   ├── prediction.py      # 预测记录表
│   │   │   ├── train_task.py      # 训练任务表
│   │   │   ├── ai_cache.py        # AI 分析缓存表
│   │   │   ├── news_cache.py      # 新闻缓存表
│   │   │   └── data_status.py     # 数据新鲜度状态表
│   │   │
│   │   └── services/              # 业务逻辑层
│   │       ├── __init__.py
│   │       │
│   │       ├── data/
│   │       │   ├── __init__.py
│   │       │   ├── akshare_client.py     # AKShare 统一封装（重试+超时）
│   │       │   ├── nav_service.py        # 基金净值获取与缓存
│   │       │   ├── index_service.py      # 指数数据获取
│   │       │   ├── holdings_service.py   # 持仓数据获取（雪球季报）
│   │       │   ├── realtime_service.py   # 新浪实时行情
│   │       │   ├── macro_service.py      # 宏观数据（利率/汇率/资金流）
│   │       │   └── news_service.py       # 新闻聚合（财联社+东财）
│   │       │
│   │       ├── fund/
│   │       │   ├── __init__.py
│   │       │   ├── profile_service.py    # 基金画像（雪球接口+三级分类）
│   │       │   ├── routing_service.py    # fund_type → pipeline 路由
│   │       │   └── normalizer.py         # 基金代码输入标准化
│   │       │
│   │       ├── features/
│   │       │   ├── __init__.py
│   │       │   ├── feature_service.py    # 特征构建主入口
│   │       │   ├── technical.py          # 技术因子（动量/波动率/均线）
│   │       │   ├── benchmark.py          # 基准暴露因子（Beta/跟踪误差）
│   │       │   ├── equity_features.py    # 偏股专用增强特征
│   │       │   ├── bond_features.py      # 债券物理先验特征
│   │       │   ├── macro_features.py     # 宏观经济特征
│   │       │   ├── calendar.py           # 日历效应因子
│   │       │   └── screening.py          # IC/VIF/ICIR 因子筛选
│   │       │
│   │       ├── model/
│   │       │   ├── __init__.py
│   │       │   ├── trainer.py            # 模型训练主流程
│   │       │   ├── ensemble.py           # Stacking 集成
│   │       │   ├── walk_forward.py       # Walk-Forward CV（动态参数）
│   │       │   ├── conformal.py          # 保形预测置信区间
│   │       │   ├── constraints.py        # 净值约束规则
│   │       │   ├── cold_start.py         # 冷启动群体模型
│   │       │   └── versioning.py         # 模型版本管理
│   │       │
│   │       ├── predict/
│   │       │   ├── __init__.py
│   │       │   ├── prediction_service.py # T+1 预测主流程
│   │       │   ├── intraday_service.py   # T 日盘中估算
│   │       │   └── shap_service.py       # SHAP 因子贡献解释
│   │       │
│   │       ├── ai/
│   │       │   ├── __init__.py
│   │       │   ├── llm_client.py         # 统一 LLM HTTP 客户端
│   │       │   ├── provider_router.py    # GLM/SiliconFlow 路由
│   │       │   ├── analysis_service.py   # AI 分析主服务
│   │       │   └── templates/
│   │       │       ├── __init__.py
│   │       │       ├── base.py           # 通用模板基类
│   │       │       ├── equity.py         # 偏股/主动股票模板
│   │       │       ├── bond.py           # 债券型模板
│   │       │       ├── index.py          # 指数/ETF 模板
│   │       │       └── mixed.py          # 平衡/灵活混合模板
│   │       │
│   │       └── task/
│   │           ├── __init__.py
│   │           ├── task_service.py       # 异步训练任务队列
│   │           └── update_service.py     # 每日数据更新调度
│   │
│   ├── data/
│   │   ├── raw/
│   │   │   ├── fund_nav/             # {fund_code}.csv 基金净值
│   │   │   ├── holdings/             # {fund_code}.csv 持仓数据
│   │   │   └── index/                # {index_code}.csv 指数数据
│   │   └── processed/                # 特征工程后的数据集
│   │
│   ├── models/
│   │   └── {fund_code}/
│   │       ├── model_{YYYYMMDD}.pkl   # 带日期的模型文件
│   │       ├── latest.json           # 指向当前激活版本
│   │       ├── metrics.json          # 训练指标
│   │       ├── selected_features.json # 筛选后的特征列表
│   │       └── versions.json         # 历史版本记录
│   │
│   ├── logs/
│   │   ├── app.log
│   │   ├── api.jsonl
│   │   ├── train.log
│   │   ├── error.log
│   │   ├── audit.jsonl
│   │   └── perf.jsonl
│   │
│   └── tests/
│       ├── test_nav_service.py
│       ├── test_feature_service.py
│       ├── test_prediction_service.py
│       ├── test_ai_analysis.py
│       └── test_normalizer.py
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── main.js                   # Vue 应用入口
        ├── App.vue                   # 根组件（含路由出口）
        │
        ├── router/
        │   └── index.js              # Vue Router 配置
        │
        ├── stores/                   # Pinia 状态管理
        │   ├── index.js
        │   ├── fund.js               # 基金状态
        │   ├── predict.js            # 预测状态
        │   ├── train.js              # 训练任务状态
        │   └── app.js                # 全局应用状态（主题/加载）
        │
        ├── api/                      # Axios 请求封装
        │   ├── index.js              # Axios 实例 + 拦截器
        │   ├── fund.js               # 基金相关请求
        │   ├── train.js              # 训练请求
        │   ├── predict.js            # 预测请求
        │   ├── intraday.js           # 盘中估算请求
        │   ├── ai.js                 # AI 分析请求
        │   ├── backtest.js           # 回测请求
        │   └── admin.js              # 管理员请求
        │
        ├── views/                    # 页面组件
        │   ├── Dashboard.vue         # 决策中心首页
        │   ├── Predict.vue           # T+1 智能预测
        │   ├── Intraday.vue          # T 日盘中估算
        │   ├── Train.vue             # 模型训练
        │   ├── Backtest.vue          # 回测诊断
        │   ├── Profile.vue           # 基金画像
        │   ├── Compare.vue           # 多基金对比
        │   ├── ModelMonitor.vue      # 模型监控
        │   └── AdminDataStatus.vue   # 数据管理
        │
        ├── components/
        │   ├── layout/
        │   │   ├── AppLayout.vue     # 整体布局容器
        │   │   ├── Sidebar.vue       # 左侧导航
        │   │   └── Topbar.vue        # 顶部栏（含基金搜索）
        │   │
        │   ├── fund/
        │   │   ├── FundCodeInput.vue    # 统一基金代码输入组件（含容错）
        │   │   ├── FundHealthCard.vue   # 基金健康度卡片
        │   │   └── FundTypeBadge.vue    # 基金类型标签
        │   │
        │   ├── predict/
        │   │   ├── PredictResultCard.vue  # 预测结果主卡
        │   │   ├── IntervalChart.vue      # 置信区间可视化
        │   │   ├── DirectionGauge.vue     # 涨跌方向仪表
        │   │   └── ShapPanel.vue          # 因子贡献 SHAP 展示
        │   │
        │   ├── intraday/
        │   │   ├── IntradayCard.vue       # 盘中估算主卡
        │   │   ├── HoldingsTable.vue      # 重仓股贡献表格
        │   │   └── MarketStatusBadge.vue  # 市场开收盘状态
        │   │
        │   ├── ai/
        │   │   ├── AiAnalysisPanel.vue    # AI 分析完整面板
        │   │   ├── NewsSourceList.vue     # 新闻来源列表
        │   │   └── ActionBadge.vue        # 操作建议徽章
        │   │
        │   ├── chart/
        │   │   ├── NavTrendChart.vue      # 净值走势图
        │   │   ├── AccuracyTrendChart.vue # 准确率趋势图
        │   │   ├── BacktestChart.vue      # 回测对比图
        │   │   └── RadarChart.vue         # 雷达图（区间覆盖率）
        │   │
        │   └── common/
        │       ├── LoadingSkeleton.vue    # 骨架屏
        │       ├── EmptyState.vue         # 空状态
        │       ├── ConfidenceBadge.vue    # 置信度徽章
        │       └── DataFreshnessTag.vue   # 数据时效标签
        │
        ├── utils/
        │   ├── request.js             # Axios 拦截器配置
        │   ├── logger.js              # 前端结构化日志
        │   ├── format.js             # 数字/日期格式化
        │   ├── fundValidator.js       # 基金代码前端验证
        │   └── marketTime.js          # 交易时间判断工具
        │
        └── assets/
            └── styles/
                ├── variables.scss    # CSS 变量（主题色/字体）
                ├── global.scss       # 全局样式重置
                └── element.scss     # Element Plus 主题覆盖
```

---

## 3. 数据库设计

### 3.1 SQLite 初始化配置

```sql
-- 开启 WAL 模式（允许并发读写）
PRAGMA journal_mode = WAL;
-- 外键约束
PRAGMA foreign_keys = ON;
-- 缓存大小
PRAGMA cache_size = -65536;  -- 64MB
```

### 3.2 全部表定义

```sql
-- ========================================
-- 基金净值历史
-- ========================================
CREATE TABLE IF NOT EXISTS fund_nav (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code     TEXT    NOT NULL,
    nav_date      TEXT    NOT NULL,   -- YYYY-MM-DD
    nav           REAL    NOT NULL,   -- 单位净值
    acc_nav       REAL,               -- 累计净值
    daily_return  REAL,               -- 日涨跌幅（%）
    adj_nav       REAL,               -- 复权净值（分红调整后）
    source        TEXT DEFAULT 'em',  -- 数据来源：em/xq
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, nav_date)
);
CREATE INDEX idx_fund_nav_code_date ON fund_nav(fund_code, nav_date DESC);

-- ========================================
-- 预测记录（每次预测存一条）
-- ========================================
CREATE TABLE IF NOT EXISTS prediction (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code            TEXT    NOT NULL,
    predict_date         TEXT    NOT NULL,   -- 预测发起日期
    target_date          TEXT    NOT NULL,   -- 预测目标日期（T+1）
    predicted_return     REAL    NOT NULL,   -- 预测涨跌幅
    lower_bound          REAL    NOT NULL,   -- 置信区间下界
    upper_bound          REAL    NOT NULL,   -- 置信区间上界
    direction            TEXT    NOT NULL,   -- up / down / neutral
    direction_prob       REAL    NOT NULL,   -- 上涨概率
    confidence_level     REAL    DEFAULT 0.90,
    model_type           TEXT,               -- ridge/lgbm/stacking等
    model_version        TEXT,               -- 使用的模型版本日期
    features_used        INTEGER,            -- 使用的特征数
    fund_type            TEXT,               -- 预测时的基金类型
    -- 事后验证字段（收盘后填充）
    actual_return        REAL,               -- 实际涨跌幅
    error                REAL,               -- 绝对误差
    direction_correct    INTEGER,            -- 1=方向正确 0=错误
    interval_covered     INTEGER,            -- 1=实际值在区间内
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, predict_date, target_date)
);
CREATE INDEX idx_prediction_code ON prediction(fund_code, predict_date DESC);

-- ========================================
-- 训练任务
-- ========================================
CREATE TABLE IF NOT EXISTS train_task (
    id             TEXT    PRIMARY KEY,   -- UUID
    fund_code      TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'pending',
    -- pending / running / success / failed / cancelled
    force_retrain  INTEGER DEFAULT 0,
    progress       INTEGER DEFAULT 0,    -- 0-100
    log_text       TEXT,                 -- 训练日志（追加写入）
    metrics_json   TEXT,                 -- 训练完成后的指标 JSON
    model_version  TEXT,                 -- 生成的模型版本
    error_message  TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at     TIMESTAMP,
    finished_at    TIMESTAMP
);
CREATE INDEX idx_task_fund ON train_task(fund_code, created_at DESC);

-- ========================================
-- AI 分析缓存（当日有效）
-- ========================================
CREATE TABLE IF NOT EXISTS ai_analysis_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code     TEXT    NOT NULL,
    trade_date    TEXT    NOT NULL,   -- YYYY-MM-DD
    analysis_json TEXT    NOT NULL,   -- 完整分析结果 JSON
    provider_used TEXT,               -- glm / siliconflow
    model_used    TEXT,
    news_count    INTEGER DEFAULT 0,
    tokens_used   INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, trade_date)
);

-- ========================================
-- 新闻缓存（10分钟有效）
-- ========================================
CREATE TABLE IF NOT EXISTS news_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT    NOT NULL UNIQUE,  -- news:{fund_code}:{YYYYMMDD_HHmm10}
    news_json   TEXT    NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 数据新鲜度状态（管理员页面用）
-- ========================================
CREATE TABLE IF NOT EXISTS data_status (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type      TEXT    NOT NULL,   -- fund_nav / index / holdings / macro
    identifier     TEXT    NOT NULL,   -- 基金代码 或 指数代码
    latest_date    TEXT,               -- 最新数据日期
    row_count      INTEGER DEFAULT 0,
    last_updated   TIMESTAMP,
    status         TEXT DEFAULT 'ok', -- ok / stale / error
    UNIQUE(data_type, identifier)
);

-- ========================================
-- 基金画像缓存（避免频繁调用 AKShare 雪球接口）
-- ========================================
CREATE TABLE IF NOT EXISTS fund_profile_cache (
    fund_code     TEXT    PRIMARY KEY,
    fund_name     TEXT    NOT NULL,
    full_name     TEXT,
    fund_type_raw TEXT,               -- AKShare 原始类型字符串
    fund_type     TEXT,               -- 系统分类后的类型枚举
    manager       TEXT,
    company       TEXT,
    size_text     TEXT,               -- "27.30亿"
    benchmark     TEXT,
    invest_strategy TEXT,
    rating        TEXT,
    established   TEXT,               -- 成立日期
    skip_prediction INTEGER DEFAULT 0, -- 1=货币基金跳过
    classification_confidence REAL,   -- 0-1 分类置信度
    profile_json  TEXT,               -- 完整原始数据 JSON
    cached_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code)
);
```

---

## 4. AKShare 接口清单

### 4.1 基金基本信息（雪球，优先使用）

```python
import akshare as ak

# ★ 雪球基金基本信息（类型/经理/规模/策略/基准）
# 用途：基金画像页、分类路由
df = ak.fund_individual_basic_info_xq(symbol="000001")
# 返回字段：基金代码/基金名称/基金全称/成立时间/最新规模/
#           基金公司/基金经理/托管银行/基金类型/评级机构/
#           基金评级/投资策略/投资目标/业绩比较基准

# 雪球基金 NAV 历史（精度高，含复权）
df = ak.fund_open_fund_info_xq(symbol="000001", indicator="单位净值走势")
# 返回：date, nav, acc_nav

# 雪球基金规模变动
df = ak.fund_open_fund_info_xq(symbol="000001", indicator="规模变动")
```

### 4.2 基金净值（东方财富，作为主力和补充）

```python
# 东方财富历史净值（最完整）
# 用途：训练数据主要来源
df = ak.fund_open_fund_info_em(fund="000001", indicator="单位净值走势")
# 返回：净值日期, 单位净值, 日增长率, 申购状态, 赎回状态

# 东方财富实时估值（T日盘中）
df = ak.fund_em_value_estimation(fund_code="000001")
# 返回：基金代码, 估算净值, 估算涨跌幅, 估算时间

# 东方财富基金规模
df = ak.fund_open_fund_info_em(fund="000001", indicator="规模变动")
```

### 4.3 持仓数据（雪球季报）

```python
# ★ 雪球季报持仓（含权重，最关键的盘中估算数据）
# 用途：T日盘中加权估算净值
df = ak.fund_portfolio_hold_em(symbol="000001", date="2024")
# 返回：股票代码/股票名称/占净值比例/持股数/持股市值/季度

# 东方财富持仓（备用）
df = ak.fund_portfolio_holdings_em(symbol="000001")
```

### 4.4 实时行情（新浪，核心接口）

```python
# ★★★ 新浪实时股票行情（T日盘中估算核心）
# 直接 HTTP 请求，不通过 AKShare 封装（更快更稳定）
import requests

def get_sina_realtime(stock_codes: list[str]) -> dict:
    """
    stock_codes: ['600519', '000858', ...]  纯数字代码
    自动添加 sh/sz 前缀
    """
    formatted = []
    for code in stock_codes:
        if code.startswith('6') or code.startswith('5'):
            formatted.append(f"sh{code}")
        else:
            formatted.append(f"sz{code}")
    
    url = f"http://hq.sinajs.cn/list={','.join(formatted)}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(url, headers=headers, timeout=5)
    resp.encoding = 'gbk'
    
    result = {}
    for line in resp.text.strip().split('\n'):
        if 'hq_str_' not in line or '""' in line:
            continue
        # 解析：var hq_str_sh600519="贵州茅台,1800.00,1780.00,..."
        code_part = line.split('"')[0].replace('var hq_str_', '').strip('=')
        actual_code = code_part.replace('sh', '').replace('sz', '')
        data = line.split('"')[1].split(',')
        if len(data) < 32:
            continue
        result[actual_code] = {
            'name':       data[0],
            'open':       float(data[1]) if data[1] else 0,
            'prev_close': float(data[2]) if data[2] else 0,
            'price':      float(data[3]) if data[3] else 0,
            'high':       float(data[4]) if data[4] else 0,
            'low':        float(data[5]) if data[5] else 0,
            'pct_change': (float(data[3]) - float(data[2])) / float(data[2])
                          if data[2] and float(data[2]) > 0 else 0,
            'volume':     int(data[8]) if data[8] else 0,
            'update_time': f"{data[30]} {data[31]}" if len(data) > 31 else ''
        }
    return result

# ★ 新浪指数实时行情（沪深300等）
def get_sina_index_realtime() -> dict:
    index_codes = {
        'sh000300': 'hs300',    # 沪深300
        'sh000001': 'sh',       # 上证指数
        'sz399001': 'sz',       # 深证成指
        'sz399006': 'cyb',      # 创业板指
        'sh000688': 'kcb',      # 科创50
        'sh000905': 'zz500',    # 中证500
        'sh000852': 'zz1000',   # 中证1000
    }
    # 同上方 get_sina_realtime 逻辑，解析指数数据
    ...
```

### 4.5 指数历史数据

```python
# 沪深300历史
df = ak.stock_zh_index_daily(symbol="sh000300")
# 返回：date, open, high, low, close, volume

# 中证500历史
df = ak.stock_zh_index_daily(symbol="sh000905")

# 创业板指历史
df = ak.stock_zh_index_daily(symbol="sz399006")

# 所有主要指数清单
INDEX_MAP = {
    "hs300":  "sh000300",  # 沪深300
    "zz500":  "sh000905",  # 中证500
    "zz1000": "sh000852",  # 中证1000
    "cyb":    "sz399006",  # 创业板指
    "kcb50":  "sh000688",  # 科创50
    "sz50":   "sh000016",  # 上证50
    "red":    "sh000015",  # 上证红利
    "chinext":"sz399006",  # 创业板综
}
```

### 4.6 宏观数据

```python
# 中美国债收益率
df = ak.bond_zh_us_rate(start_date="20240101")
# 返回：日期/中国国债收益率2年/中国国债收益率10年/...

# Shibor 利率（债基流动性因子）
df = ak.macro_china_shibor_all()
# 返回：日期/隔夜/1周/2周/1月/3月/...

# 人民币汇率
df = ak.currency_boc_sina(currency="USD")
# 返回：日期/现汇买入价/现钞买入价/现汇卖出价/现钞卖出价/中行折算价

# 北向资金净流入（情绪因子）
df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")
# 返回：日期/净买入额（亿元）
```

### 4.7 新闻聚合

```python
# ★ 财联社电报（最快的市场快讯）
df = ak.stock_telegraph_cls_em()
# 返回：发布时间/内容/标签

# 东方财富个股相关新闻
# 注意：symbol 传股票代码（非基金代码），用重仓股代码查询
df = ak.stock_news_em(symbol="600519")
# 返回：文章标题/发布时间/文章来源/文章链接

# 同花顺财经快讯（补充）
df = ak.stock_news_ths(symbol="600519")
```

### 4.8 ETF 折溢价（ETF 专用）

```python
# ETF 实时折溢价率
df = ak.fund_etf_fund_daily_em()
# 返回：基金代码/基金简称/最新价/折溢价率/...
```

---

## 5. 后端 API 完整设计

### 5.1 统一响应格式

所有接口返回统一格式：

```python
# schemas/common.py

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[dict] = None

class ErrorDetail(BaseModel):
    code: str       # 错误代码枚举，如 INSUFFICIENT_DATA
    message: str    # 人类可读的错误描述
    status: int     # HTTP 状态码

# 成功响应示例：
# {"ok": true, "data": {...}}

# 失败响应示例：
# {"ok": false, "error": {"code": "MODEL_NOT_FOUND", "message": "...", "status": 404}}
```

### 5.2 完整接口清单（含请求/响应结构）

---

#### `POST /api/v1/fund/predict`

T+1 净值预测。

**请求体**：
```json
{
  "fund_code": "110011",
  "force_retrain": false
}
```

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "fund_name": "易方达中小盘混合",
    "fund_type": "equity_active",
    "predict_date": "2026-05-26",
    "target_date": "2026-05-27",
    "predicted_return": 0.0035,
    "predicted_nav": 1.8765,
    "prev_nav": 1.8699,
    "confidence_interval": {
      "lower": -0.0082,
      "upper": 0.0152,
      "confidence_level": 0.90
    },
    "direction": "up",
    "direction_probability": 0.62,
    "confidence": "medium",
    "model_info": {
      "model_type": "stacking",
      "base_models": ["ridge", "lgbm"],
      "mae": 0.0041,
      "direction_accuracy": 0.64,
      "features_used": 38,
      "trained_date": "2026-05-24",
      "model_version": "20260524",
      "wfcv_rounds": 9
    },
    "constraint_info": {
      "is_clipped": false,
      "original_return": 0.0035,
      "limit": 0.20
    },
    "special_period_adjustments": [
      {"reason": "季报披露窗口", "confidence_penalty": -0.15}
    ],
    "fund_health": {
      "data_sufficiency": "充足",
      "data_days": 845,
      "data_freshness": "最新",
      "latest_nav_date": "2026-05-26",
      "model_age_days": 2,
      "prediction_reliability": "中等",
      "warnings": ["处于季报披露窗口期，预测置信度已下调"]
    },
    "shap_top_factors": [
      {"factor": "fund_ret_lag1", "contribution": 0.0018, "direction": "正向", "display": "昨日动量"},
      {"factor": "beta_hs300",    "contribution": 0.0012, "direction": "正向", "display": "大盘Beta"},
      {"factor": "vol_ratio_20d", "contribution": -0.0008,"direction": "负向", "display": "波动率"}
    ]
  }
}
```

**错误响应 (404)**：
```json
{
  "ok": false,
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "基金 110011 尚未训练模型，请先前往训练页面训练",
    "status": 404,
    "action_hint": "train"
  }
}
```

---

#### `GET /api/v1/fund/{code}/profile`

获取基金完整画像（调用雪球接口）。

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "000001",
    "fund_name": "华夏成长混合",
    "full_name": "华夏成长前收费",
    "fund_type_raw": "混合型-偏股",
    "fund_type": "hybrid_equity",
    "classification_confidence": 0.85,
    "established": "2001-12-18",
    "size_text": "27.30亿",
    "company": "华夏基金管理有限公司",
    "manager": "王泽实 万方方",
    "benchmark": "本基金暂不设业绩比较基准",
    "invest_strategy": "重点投资于预期利润或收入具有良好增长潜力的成长型上市公司...",
    "rating": "一星基金",
    "skip_prediction": false,
    "asset_allocation": {
      "equity_ratio": 0.85,
      "bond_ratio": 0.05,
      "cash_ratio": 0.10
    },
    "top10_holdings": [
      {"rank": 1, "code": "600519", "name": "贵州茅台", "weight": 0.0892, "quarter": "2026Q1"},
      {"rank": 2, "code": "000858", "name": "五粮液",  "weight": 0.0754, "quarter": "2026Q1"}
    ],
    "holdings_freshness": {
      "quarter": "2026Q1",
      "report_date": "2026-04-30",
      "days_since_report": 26,
      "freshness_level": "fresh",
      "freshness_label": "数据较新"
    },
    "data_status": {
      "nav_latest_date": "2026-05-26",
      "nav_total_days": 845,
      "has_model": true,
      "model_trained_date": "2026-05-24"
    }
  }
}
```

---

#### `GET /api/v1/fund/search`

基金名称模糊搜索（支持名称/代码两种输入）。

**查询参数**：`q=华夏成长`（或 `q=000001`）

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "results": [
      {
        "fund_code": "000001",
        "fund_name": "华夏成长混合",
        "fund_type_raw": "混合型-偏股",
        "fund_type": "hybrid_equity",
        "company": "华夏基金",
        "size_text": "27.30亿"
      }
    ],
    "total": 1,
    "query": "华夏成长"
  }
}
```

---

#### `POST /api/v1/fund/validate`

基金代码验证与标准化（输入容错）。

**请求体**：
```json
{"raw_input": "1100 "}
```

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "raw_input": "1100 ",
    "normalized": "001100",
    "is_valid": true,
    "fund_name": "易方达沪深300ETF联接",
    "fund_type": "index_equity",
    "skip_prediction": false,
    "normalization_steps": ["trim_whitespace", "left_pad_zeros"]
  }
}
```

---

#### `POST /api/v1/train`

创建训练任务（异步，立即返回任务 ID）。

**请求体**：
```json
{
  "fund_code": "110011",
  "force_retrain": false
}
```

**响应 (202)**：
```json
{
  "ok": true,
  "data": {
    "task_id": "a3f8c2d1e4b5",
    "fund_code": "110011",
    "status": "pending",
    "message": "训练任务已加入队列",
    "position_in_queue": 1
  }
}
```

---

#### `GET /api/v1/tasks/{task_id}`

轮询任务状态（前端每2秒调用一次）。

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "task_id": "a3f8c2d1e4b5",
    "fund_code": "110011",
    "status": "running",
    "progress": 65,
    "current_stage": "Walk-Forward CV (Round 7/9)",
    "log_tail": [
      "[12:34:21] 数据加载完成，共 845 行",
      "[12:34:22] 特征构建完成，共 82 个原始特征",
      "[12:34:22] 因子筛选：保留 41 个特征",
      "[12:34:23] 开始 Walk-Forward CV (9 轮)...",
      "[12:34:31] Round 7 完成 MAE=0.0038"
    ],
    "created_at": "2026-05-26T12:34:20Z",
    "started_at": "2026-05-26T12:34:20Z",
    "estimated_remaining_seconds": 15
  }
}
```

**完成响应**（status=success）：
```json
{
  "ok": true,
  "data": {
    "task_id": "a3f8c2d1e4b5",
    "fund_code": "110011",
    "status": "success",
    "progress": 100,
    "metrics": {
      "best_model": "stacking",
      "valid_mae": 0.0038,
      "valid_rmse": 0.0051,
      "direction_accuracy": 0.64,
      "wfcv_rounds": 9,
      "features_used": 41,
      "model_version": "20260526",
      "train_rows": 845
    },
    "finished_at": "2026-05-26T12:34:47Z"
  }
}
```

---

#### `GET /api/v1/tasks`

训练任务列表。

**查询参数**：`fund_code=110011`（可选）、`limit=20`、`offset=0`

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "tasks": [
      {
        "task_id": "a3f8c2d1e4b5",
        "fund_code": "110011",
        "fund_name": "易方达中小盘混合",
        "status": "success",
        "created_at": "2026-05-26T12:34:20Z",
        "finished_at": "2026-05-26T12:34:47Z",
        "duration_seconds": 27,
        "valid_mae": 0.0038
      }
    ],
    "total": 1
  }
}
```

---

#### `POST /api/v1/intraday/{code}`

T 日盘中净值估算。

**请求体**：
```json
{"mode": "holdings"}
```
`mode` 可选：`holdings`（持仓加权，精度高）/ `index`（指数回归，始终可用）/ `auto`（系统自动选择）

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "fund_name": "易方达中小盘混合",
    "estimated_nav": 1.8732,
    "prev_nav": 1.8699,
    "estimated_return": 0.00176,
    "estimated_return_pct": 0.18,
    "confidence_interval": {
      "lower": -0.0045,
      "upper": 0.0081
    },
    "confidence": "medium",
    "method": "holdings_weighted",
    "method_display": "持仓加权法",
    "market_session": {
      "is_trading": true,
      "session": "continuous",
      "note": "交易中（距收盘 47 分钟）"
    },
    "holdings_used": [
      {
        "rank": 1,
        "code": "600519",
        "name": "贵州茅台",
        "weight": 0.0892,
        "price": 1802.0,
        "prev_close": 1790.0,
        "pct_change": 0.0067,
        "contribution": 0.000598
      },
      {
        "rank": 2,
        "code": "000858",
        "name": "五粮液",
        "weight": 0.0754,
        "price": 145.2,
        "prev_close": 146.5,
        "pct_change": -0.0089,
        "contribution": -0.000671
      }
    ],
    "holdings_freshness": {
      "quarter": "2026Q1",
      "days_since_report": 26,
      "freshness_level": "fresh"
    },
    "index_comparison": {
      "hs300_return": 0.0021,
      "fund_vs_hs300": 0.00034
    },
    "timestamp": "2026-05-26T14:13:22Z"
  }
}
```

---

#### `GET /api/v1/fund/{code}/backtest`

回测历史预测准确率。

**查询参数**：`days=90`（回测天数，默认90）

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "fund_name": "易方达中小盘混合",
    "period": {"start": "2026-02-25", "end": "2026-05-26", "days": 90},
    "summary": {
      "total_predictions": 62,
      "mae": 0.0041,
      "rmse": 0.0058,
      "direction_accuracy": 0.645,
      "interval_coverage_80": 0.823,
      "interval_coverage_90": 0.903,
      "pearson_corr": 0.412,
      "spearman_corr": 0.398
    },
    "by_market_state": {
      "bull":  {"days": 28, "direction_accuracy": 0.714, "mae": 0.0035},
      "bear":  {"days": 19, "direction_accuracy": 0.526, "mae": 0.0058},
      "range": {"days": 15, "direction_accuracy": 0.600, "mae": 0.0043}
    },
    "daily_records": [
      {
        "date": "2026-05-26",
        "predicted_return": 0.0035,
        "actual_return": 0.0028,
        "error": 0.0007,
        "direction_correct": true,
        "in_interval": true
      }
    ]
  }
}
```

---

#### `POST /api/v1/ai/analysis`

调用 AI 生成分析报告（异步，前端轮询或 SSE）。

**请求体**：
```json
{
  "fund_code": "110011",
  "context": {
    "estimated_return": 0.00176,
    "lower_bound": -0.0045,
    "upper_bound": 0.0081,
    "source": "intraday"
  },
  "refresh": false
}
```

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "trade_date": "2026-05-26",
    "analysis": {
      "summary": "今日白酒板块受消费数据提振，贵州茅台逆势上涨0.67%，对本基金净值形成正向贡献。但五粮液小幅下跌拖累整体，综合来看今日净值预计小幅上涨。",
      "key_drivers": [
        {"factor": "贵州茅台", "direction": "正向", "desc": "逆势上涨0.67%，权重最高，贡献约+0.06%"},
        {"factor": "五粮液",   "direction": "负向", "desc": "下跌0.89%，拖累约-0.07%"}
      ],
      "risk_factors": [
        "北向资金今日净流出，外资情绪偏谨慎",
        "大盘整体承压，沪深300跌0.21%"
      ],
      "suggested_action": "持有",
      "suggested_action_reason": "净值涨跌有限，主逻辑未变",
      "disclaimer": "以上分析由AI生成，仅供参考，不构成投资建议"
    },
    "news_used": [
      {
        "title": "消费数据超预期，白酒板块全线上涨",
        "source": "财联社",
        "published_at": "2026-05-26T09:45:00Z",
        "relevance_score": 0.88,
        "matched_keywords": ["白酒", "消费"]
      }
    ],
    "holdings_freshness": {
      "quarter": "2026Q1",
      "days_since_report": 26,
      "freshness_level": "fresh"
    },
    "provider_used": "glm",
    "model_used": "glm-4-flash",
    "tokens_used": 1024,
    "cached": false,
    "generated_at": "2026-05-26T14:13:35Z"
  }
}
```

---

#### `GET /api/v1/fund/{code}/news`

获取基金相关新闻（不调用AI，快速返回）。

**查询参数**：`limit=5`、`source=all`

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "news": [
      {
        "title": "消费数据超预期，白酒板块全线上涨",
        "content": "国家统计局今日公布消费数据...",
        "source": "财联社",
        "source_type": "cls",
        "published_at": "2026-05-26T09:45:00Z",
        "relevance_score": 0.88,
        "matched_keywords": ["白酒", "消费"]
      }
    ],
    "total": 3,
    "fetched_at": "2026-05-26T14:13:00Z"
  }
}
```

---

#### `GET /api/v1/dashboard/stats`

首页统计数据。

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "trained_models": 12,
    "avg_direction_accuracy": 0.632,
    "today_predictions": 8,
    "avg_response_ms": 124,
    "data_freshness": {
      "stale_funds": 2,
      "total_funds": 12
    }
  }
}
```

---

#### `GET /api/v1/dashboard/recent-predictions`

最近预测记录。

**查询参数**：`limit=10`

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "predictions": [
      {
        "fund_code": "110011",
        "fund_name": "易方达中小盘混合",
        "predict_date": "2026-05-26",
        "predicted_return": 0.0035,
        "direction": "up",
        "direction_probability": 0.62,
        "confidence": "medium",
        "actual_return": null,
        "is_correct": null
      }
    ]
  }
}
```

---

#### `GET /api/v1/admin/data-status`

数据新鲜度状态。

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "summary": {
      "total_funds": 12,
      "stale_funds": 2,
      "total_index": 7,
      "last_update_run": "2026-05-26T17:35:00Z"
    },
    "fund_status": [
      {
        "fund_code": "110011",
        "fund_name": "易方达中小盘混合",
        "nav_latest_date": "2026-05-26",
        "nav_rows": 845,
        "holdings_quarter": "2026Q1",
        "holdings_days_old": 26,
        "has_model": true,
        "model_trained_date": "2026-05-24",
        "model_age_days": 2,
        "overall_status": "ok"
      }
    ],
    "index_status": [
      {
        "index_code": "sh000300",
        "index_name": "沪深300",
        "latest_date": "2026-05-26",
        "rows": 5200,
        "status": "ok"
      }
    ]
  }
}
```

---

#### `POST /api/v1/admin/update-data`

手动触发数据更新（指定基金或全量）。

**请求体**：
```json
{
  "fund_codes": ["110011", "000001"],  // 空数组表示全量更新
  "update_nav": true,
  "update_holdings": true,
  "update_index": true
}
```

**响应 (202)**：
```json
{
  "ok": true,
  "data": {
    "update_task_id": "upd_20260526_143000",
    "message": "数据更新任务已启动",
    "estimated_seconds": 45
  }
}
```

---

#### `GET /api/v1/ai/provider-status`

AI Provider 可用性检测。

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "primary": {
      "provider": "glm",
      "model": "glm-4-flash",
      "status": "available",
      "latency_ms": 312
    },
    "fallback": {
      "provider": "siliconflow",
      "model": "Qwen/Qwen2.5-7B-Instruct",
      "status": "available",
      "latency_ms": 521
    },
    "checked_at": "2026-05-26T14:10:00Z"
  }
}
```

---

#### `POST /api/v1/fund/batch-predict`

批量预测（最多10只）。

**请求体**：
```json
{"fund_codes": ["110011", "000001", "161725"]}
```

**响应 (200)**：
```json
{
  "ok": true,
  "data": {
    "results": [
      {
        "fund_code": "110011",
        "fund_name": "易方达中小盘混合",
        "predicted_return": 0.0035,
        "direction": "up",
        "direction_probability": 0.62,
        "confidence": "medium",
        "status": "success"
      },
      {
        "fund_code": "000001",
        "status": "error",
        "error": {"code": "MODEL_NOT_FOUND", "message": "尚未训练模型"}
      }
    ],
    "success_count": 2,
    "error_count": 1
  }
}
```

---

### 5.3 HTTP 状态码规范

| 场景 | 状态码 | code 字段 |
|---|---|---|
| 成功 | 200 | — |
| 异步任务已接收 | 202 | — |
| 基金代码不存在/无法获取数据 | 502 | DATA_FETCH_ERROR |
| 历史数据不足（<220行） | 422 | INSUFFICIENT_DATA |
| 模型文件不存在 | 404 | MODEL_NOT_FOUND |
| 训练失败 | 500 | TRAINING_ERROR |
| 预测计算异常 | 500 | PREDICTION_ERROR |
| AI Provider 不可用 | 503 | AI_PROVIDER_UNAVAILABLE |
| API Key 未配置 | 503 | AI_NOT_CONFIGURED |
| 参数校验失败 | 422 | VALIDATION_ERROR |
| 货币基金无需预测 | 200 | — （特殊 data.skip=true） |

---

## 6. 后端服务层详细设计

### 6.1 基金代码标准化（`fund/normalizer.py`）

处理所有用户输入，在任何业务逻辑执行前调用。

```
输入: raw_input（任意格式的用户输入）
  │
  ├─ Step 1: 去除空白字符（strip + 全角空格替换）
  │   "110011 " → "110011"
  │   " 1 1 0 0 1 1" → "110011"
  │
  ├─ Step 2: 去除常见后缀
  │   "000001.OF" → "000001"
  │   "000001.SH" → "000001"
  │   "sh000001"  → "000001"（保留6位数字部分）
  │
  ├─ Step 3: 纯数字补零
  │   "1100"   → "001100"（左补零至6位）
  │   "11"     → "000011"
  │
  ├─ Step 4: 格式合法性验证
  │   6位纯数字 → 通过
  │   非纯数字  → 进入名称搜索路径
  │
  ├─ Step 5: 股票代码识别（排除误输入）
  │   如果该代码在已知股票代码库中但不在基金代码库中
  │   → 返回 is_valid=false，提示"这看起来是股票代码"
  │
  └─ Step 6: 调用 AKShare 验证（最终确认）
       ak.fund_individual_basic_info_xq(symbol=normalized)
       成功 → is_valid=true，返回基金名称
       失败 → is_valid=false，返回错误提示
```

### 6.2 基金分类路由（`fund/profile_service.py`）

基于雪球接口返回数据进行三级分类。

**Level 1：业绩比较基准解析（最优先）**

```python
BENCHMARK_PATTERNS = [
    # 股票权重 > 65% → hybrid_equity
    (r"沪深300.*?(\d+)%", lambda m: "hybrid_equity" if int(m.group(1)) >= 65 else None),
    (r"中证500.*?(\d+)%", lambda m: "equity_active" if int(m.group(1)) >= 65 else None),
    
    # 纯债基准
    (r"中债.*综合", lambda _: "bond_pure"),
    (r"中证全债",   lambda _: "bond_pure"),
    
    # 可转债基准
    (r"中证转债",   lambda _: "bond_convertible"),
    
    # 均衡混合（股债各约50%）
    (r"沪深300.*50%.*中债.*50%", lambda _: "hybrid_balanced"),
    
    # 货币
    (r"货币市场基准|7天通知存款", lambda _: "money_market"),
]
```

**Level 2：基金类型字段直接映射**

```python
FUND_TYPE_MAP = {
    "混合型-偏股":  "hybrid_equity",
    "混合型-平衡":  "hybrid_balanced",
    "混合型-偏债":  "hybrid_bond",
    "混合型-灵活":  "hybrid_flexible",
    "股票型":       "equity_active",
    "债券型-纯债":  "bond_pure",
    "债券型-混合债":"bond_mixed",
    "债券型-可转债":"bond_convertible",
    "指数型-股票":  "index_equity",
    "指数型-债券":  "index_bond",
    "FOF":          "fof",
    "QDII":         "qdii",
    "货币型":       "money_market",
    # 模糊匹配兜底（字段格式不稳定时）
}
```

**Level 3：投资策略文本关键词 + 默认值**

策略文本含"成长"→ `equity_active`；含"债券"→ `bond_pure`；否则默认 `hybrid_equity`。

**分类置信度评分**：

| 命中级别 | 置信度 |
|---|---|
| Level1 且基准权重精确解析 | 0.95 |
| Level1 但权重无法解析 | 0.72 |
| Level2 精确匹配 | 0.88 |
| Level2 模糊匹配 | 0.65 |
| Level3 文本关键词 | 0.55 |
| Level3 默认值 | 0.50 |

### 6.3 数据获取层（`data/`）

**缓存层级设计**：

```
请求一个基金的净值数据
  │
  Level 1: 进程内存缓存（ThreadSafe TTLCache）
  │         TTL = 当日最后一次交易时间后失效
  │         命中 → 直接返回（<1ms）
  │
  Level 2: SQLite fund_nav 表
  │         检查最新日期是否是最近交易日
  │         命中 → 返回（<10ms）
  │
  Level 3: 本地 CSV（data/raw/fund_nav/{code}.csv）
  │         作为 SQLite 的持久化备份
  │         命中 → 读取并回填 SQLite（<50ms）
  │
  Level 4: AKShare 网络请求
            ak.fund_open_fund_info_em() 或 ak.fund_open_fund_info_xq()
            成功 → 写入 CSV + SQLite + 内存缓存
            失败 → 返回最后已知数据 + 标注 data_stale=true
```

**NAV 缓存使用线程安全的 TTLCache**：

```python
# 解决原文档中 _NAV_CACHE 全局 dict 的线程安全问题
from cachetools import TTLCache
import threading

_nav_cache = TTLCache(maxsize=500, ttl=86400)  # 最多500只基金，当日有效
_nav_lock = threading.RLock()

def get_nav_cached(fund_code: str) -> Optional[pd.DataFrame]:
    with _nav_lock:
        return _nav_cache.get(fund_code)

def set_nav_cached(fund_code: str, df: pd.DataFrame):
    with _nav_lock:
        _nav_cache[fund_code] = df
```

### 6.4 特征工程（`features/`）

按基金类型选择不同的特征集合：

**偏股混合/主动股票（`equity_active`, `hybrid_equity`）**

核心特征集（按重要性排序）：
1. 重仓股加权涨跌幅（持仓映射，最强信号）
2. 对沪深300/中证500的滚动Beta（20日）
3. 净值动量：1/5/10/20/60日收益率
4. 历史波动率：20日滚动标准差（年化）
5. 短期反转：5日收益率（均值回归信号）
6. 风格暴露：成长vs大盘（创业板-沪深300 5日均值）
7. 日历效应：月末/季末/周一/周五哑变量
8. 北向资金净流入（情绪因子）
9. RSI（14日）、MACD 柱状值
10. 持仓集中度变化（季报更新时）

**纯债/混合债（`bond_pure`, `bond_mixed`）**

核心特征集：
1. 物理先验：`-duration × Δy`（10年国债收益率变动）
2. 期限利差：10Y-2Y 国债利差
3. DR007 利率水平
4. 信用利差：AAA 企业债-国债
5. 净值动量（较短，5/10日）
6. 月末/季末效应

**指数/ETF（`index_equity`）**

不使用 ML 模型，使用规则引擎：

```
pred_return = index_return × (1 - daily_fee_rate) + tracking_error_correction

其中:
  index_return = 标的指数当日涨跌幅（实时行情或收盘数据）
  daily_fee_rate = 年管理费率 / 252（约 0.0003%/日）
  tracking_error_correction = 近20日基金-指数残差的均值（系统性偏差修正）
```

### 6.5 Walk-Forward CV（动态参数，修复原文档问题）

解决原文档中固定 24 个月训练窗口与最小样本 220 行不匹配的问题：

```
输入: 总数据行数 N
  │
  ├─ 计算可用数据天数（交易日）
  │
  ├─ 动态设置训练窗口
  │   IF N >= 500:  train_window = 500  (约2年)，最多24轮
  │   IF N >= 300:  train_window = 250  (约1年)，最多12轮
  │   IF N >= 220:  train_window = int(N * 0.55)，最多6轮
  │   IF N <  220:  raise InsufficientDataError
  │
  ├─ 动态设置验证窗口
  │   valid_window = max(40, int(train_window * 0.2))
  │
  ├─ 计算实际可运行轮数
  │   available_rounds = (N - train_window - valid_window) // step_size
  │   actual_rounds = max(3, min(available_rounds, 24))
  │   IF actual_rounds < 3: 降级为 Hold-out（最后 20% 作验证集）
  │
  ├─ 在 metrics.json 中记录:
  │   "wfcv_rounds": actual_rounds,
  │   "wfcv_degraded": actual_rounds < 6,  ← 轮次不足时标记
  │
  └─ 前端展示: 轮次 < 6 时显示黄色警告"数据量有限，置信度偏低"
```

### 6.6 冷启动机制（修复 120-220 天盲区）

解决原文档中 120-220 天基金无处理路径的问题：

```
should_use_group_model(fund_code):

  history_days = len(fund_nav_rows)

  IF history_days < 250:          ← 统一阈值，与 MIN_TRAIN_ROWS 保持余量
    RETURN (True, "group_model")  ← 全部使用群体模型，无盲区

  IF 250 <= history_days < 400:   ← 过渡阶段
    blend = (history_days - 250) / 150   ← 0.0 → 1.0 线性增长
    RETURN (True, "blended", blend)      ← 群体模型+个体微调混合

  IF history_days >= 400:
    IF has_model(fund_code):
      RETURN (False, "individual")       ← 完全使用个体模型
    ELSE:
      触发异步训练任务，当前使用群体模型临时响应
      RETURN (True, "group_model_pending_train")
```

### 6.7 模型版本管理（`model/versioning.py`）

解决原文档中模型重训直接覆盖的问题：

```
models/110011/
├── model_20260524.pkl      ← 带日期命名
├── model_20260510.pkl
├── model_20260426.pkl
├── latest.json             ← {"active": "20260524", "versions": [...]}
├── metrics.json            ← 当前激活版本的指标
├── selected_features.json  ← 当前激活版本的特征列表
└── versions.json           ← 所有版本的元数据列表

versions.json 结构:
[
  {
    "version": "20260524",
    "trained_at": "2026-05-24T12:34:47Z",
    "valid_mae": 0.0038,
    "direction_accuracy": 0.64,
    "wfcv_rounds": 9,
    "is_active": true
  },
  {
    "version": "20260510",
    ...
    "is_active": false
  }
]

保留策略: 最多保留最近 3 个版本，删除最旧的
回滚接口: POST /api/v1/fund/{code}/model/rollback
          body: {"version": "20260510"}
```

### 6.8 AI 分析服务（`ai/`）

**Provider 路由（并发策略）**：

```
接收 AI 分析请求
  │
  ├─ 1. 检查当日缓存（SQLite ai_analysis_cache）
  │       命中 → 直接返回（<10ms）
  │
  ├─ 2. 并发拉取背景数据（asyncio.gather）
  │       Task A: news_service.fetch_relevant_news(code)  ~1-3s
  │       Task B: holdings_service.get_latest(code)       ~0.5s
  │       两者同时启动，不互相等待
  │
  ├─ 3. 根据 fund_type 选择 Prompt 模板
  │
  ├─ 4. 组装 Prompt
  │
  ├─ 5. 并发调用主备 Provider（解决超时问题）
  │       asyncio.wait([primary_task, fallback_task],
  │                    return_when=FIRST_COMPLETED,
  │                    timeout=10)
  │       谁先成功用谁，取消另一个
  │       10秒内都没有响应 → AIProviderError
  │
  ├─ 6. 解析 JSON + 字段校验
  │
  ├─ 7. 添加免责声明字段
  │       analysis.disclaimer = "以上分析由AI生成，仅供参考，不构成投资建议"
  │
  ├─ 8. 写入缓存
  │
  └─ 9. 返回
```

**Prompt 使用 system + user 双角色（改进原文档设计）**：

```python
messages = [
    {
        "role": "system",
        "content": """你是一位专业的中国基金分析师助手。
你的任务是根据提供的基金数据和新闻，生成客观的市场分析。
规则：
1. 只输出合法的 JSON 格式，不加任何其他文字
2. suggested_action 只能是"增持""持有""减持""观望"之一
3. 分析要客观，不作投资承诺
4. 如持仓数据较旧，在分析中体现不确定性"""
    },
    {
        "role": "user",
        "content": assembled_prompt  # 基金数据 + 新闻
    }
]
```

同时在 Body 中加入 `"response_format": {"type": "json_object"}` 强制 JSON 输出。

### 6.9 每日数据更新调度（`task/update_service.py`）

解决原文档中无数据自动更新机制的问题：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

# 每日 17:30：拉取当日净值和行情
@scheduler.scheduled_job('cron', hour=17, minute=30, day_of_week='mon-fri')
async def daily_nav_update():
    for fund_code in get_all_fund_codes():
        await nav_service.fetch_and_store(fund_code)
    await index_service.fetch_all_indices()
    await macro_service.fetch_rates()
    logger.info("daily_update_completed")

# 每日 21:30：净值公布后，回填昨日预测误差
@scheduler.scheduled_job('cron', hour=21, minute=30, day_of_week='mon-fri')
async def backfill_prediction_errors():
    yesterday = get_last_trading_day()
    predictions = await prediction_repo.get_unverified(yesterday)
    for pred in predictions:
        actual = await nav_service.get_nav_return(pred.fund_code, yesterday)
        if actual:
            await prediction_repo.fill_actual(pred.id, actual)

# 每周六 08:00：检查模型是否需要重训
@scheduler.scheduled_job('cron', day_of_week='sat', hour=8)
async def weekly_model_health_check():
    for fund_code in get_all_fund_codes():
        model_age = get_model_age_days(fund_code)
        recent_errors = get_recent_mae(fund_code, days=5)
        historical_mae = get_historical_mae(fund_code)
        if model_age > 30 or recent_errors > historical_mae * 2:
            await task_service.enqueue_train(fund_code, reason="auto_retrain")
```

---

## 7. 前端页面详细设计

### 7.1 路由配置（`router/index.js`）

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '',           name: 'Dashboard',      component: () => import('@/views/Dashboard.vue'),
        meta: { title: '决策中心', icon: 'DataAnalysis' } },
      { path: 'predict',    name: 'Predict',        component: () => import('@/views/Predict.vue'),
        meta: { title: '智能预测', icon: 'TrendCharts' } },
      { path: 'intraday',   name: 'Intraday',       component: () => import('@/views/Intraday.vue'),
        meta: { title: 'T日盘中估算', icon: 'Timer' } },
      { path: 'train',      name: 'Train',          component: () => import('@/views/Train.vue'),
        meta: { title: '模型训练', icon: 'Setting' } },
      { path: 'backtest',   name: 'Backtest',       component: () => import('@/views/Backtest.vue'),
        meta: { title: '回测诊断', icon: 'DataLine' } },
      { path: 'compare',    name: 'Compare',        component: () => import('@/views/Compare.vue'),
        meta: { title: '多基金对比', icon: 'Grid' } },
      { path: 'profile/:code?', name: 'Profile',   component: () => import('@/views/Profile.vue'),
        meta: { title: '基金画像', icon: 'UserFilled' } },
      { path: 'monitor',    name: 'ModelMonitor',   component: () => import('@/views/ModelMonitor.vue'),
        meta: { title: '模型监控', icon: 'Monitor' } },
      { path: 'admin/data', name: 'AdminData',      component: () => import('@/views/AdminDataStatus.vue'),
        meta: { title: '数据管理', icon: 'SetUp', isAdmin: true } },
    ]
  }
]
```

### 7.2 Axios 封装（`api/index.js`）

```javascript
import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
})

// 请求拦截
request.interceptors.request.use(config => {
  config.headers['X-Request-ID'] = generateRequestId()
  config.headers['X-Client-Time'] = Date.now()
  return config
})

// 响应拦截
request.interceptors.response.use(
  response => {
    const data = response.data
    if (!data.ok) {
      // 业务层错误（HTTP 200 但 ok=false）
      handleBusinessError(data.error)
      return Promise.reject(data.error)
    }
    return data.data  // 直接返回 data 字段，简化调用方代码
  },
  error => {
    const status = error.response?.status
    const errorData = error.response?.data?.error

    if (status === 404 && errorData?.code === 'MODEL_NOT_FOUND') {
      // 特殊处理：模型不存在，引导去训练
      return Promise.reject({ ...errorData, needTrain: true })
    }

    if (status === 503) {
      ElMessage.error('服务暂时不可用，请稍后重试')
    } else if (status >= 500) {
      ElMessage.error(`服务器错误（${status}），请联系管理员`)
    }

    return Promise.reject(errorData || error)
  }
)

export default request
```

### 7.3 FundCodeInput 组件（`components/fund/FundCodeInput.vue`）

这是最关键的公共组件，所有页面统一使用。

**功能**：
- 输入时实时触发标准化（去空格、补零等）
- 输入 6 位后自动搜索并展示基金名称验证
- 支持中文名称输入（触发搜索下拉）
- 键盘回车直接触发搜索
- 显示基金类型标签（成功验证后）

```vue
<template>
  <div class="fund-code-input">
    <el-autocomplete
      v-model="inputValue"
      :fetch-suggestions="searchSuggestions"
      placeholder="输入基金代码或名称，如 110011 或 易方达"
      clearable
      @select="handleSelect"
      @keyup.enter="handleConfirm"
      :loading="validating"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
      <template #default="{ item }">
        <div class="suggestion-item">
          <span class="code">{{ item.fund_code }}</span>
          <span class="name">{{ item.fund_name }}</span>
          <FundTypeBadge :type="item.fund_type" size="small" />
        </div>
      </template>
      <template #suffix>
        <FundTypeBadge v-if="validatedFund" :type="validatedFund.fund_type" />
        <el-icon v-if="validating"><Loading /></el-icon>
      </template>
    </el-autocomplete>

    <!-- 验证结果提示 -->
    <div v-if="validatedFund && !validating" class="validation-success">
      <el-text type="success" size="small">
        ✓ {{ validatedFund.fund_name }}
        <span v-if="validatedFund.skip_prediction" class="skip-hint">
          （货币基金，无需预测净值）
        </span>
      </el-text>
    </div>

    <div v-if="validationError" class="validation-error">
      <el-text type="danger" size="small">{{ validationError }}</el-text>
      <el-link
        v-if="similarFunds.length > 0"
        type="primary"
        @click="showSimilarFunds = true"
        size="small"
      >
        查看相似基金
      </el-link>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, defineEmits, defineProps } from 'vue'
import { validateFundCode, searchFunds } from '@/api/fund'

const props = defineProps({ modelValue: String })
const emit = defineEmits(['update:modelValue', 'fund-confirmed', 'fund-cleared'])

const inputValue = ref(props.modelValue || '')
const validatedFund = ref(null)
const validationError = ref('')
const validating = ref(false)
const similarFunds = ref([])

// 防抖验证（输入停止 500ms 后触发）
let validateTimer = null
watch(inputValue, (val) => {
  clearTimeout(validateTimer)
  if (!val) {
    validatedFund.value = null
    validationError.value = ''
    emit('fund-cleared')
    return
  }
  // 6位纯数字时自动触发验证
  if (/^\d{6}$/.test(val.trim())) {
    validateTimer = setTimeout(() => validateCode(val.trim()), 500)
  }
})

async function validateCode(code) {
  validating.value = true
  validationError.value = ''
  try {
    const result = await validateFundCode(code)
    if (result.is_valid) {
      validatedFund.value = result
      emit('update:modelValue', result.normalized)
      emit('fund-confirmed', result)
    } else {
      validationError.value = result.error_message || '基金代码无效'
      similarFunds.value = result.similar_funds || []
    }
  } catch (e) {
    validationError.value = '验证失败，请检查网络'
  } finally {
    validating.value = false
  }
}

async function searchSuggestions(query, callback) {
  if (!query || query.length < 2) return callback([])
  try {
    const results = await searchFunds(query)
    callback(results)
  } catch {
    callback([])
  }
}
</script>
```

### 7.4 Dashboard 页面（`views/Dashboard.vue`）

**布局结构**：

```
Dashboard
├── 标题区（"决策中心" + 今日日期 + 市场状态徽章）
│
├── 统计卡片行（4卡，水平排列）
│   ├── 已训练模型数（含"其中X个需重训"提示）
│   ├── 平均方向准确率（近30日，带趋势箭头）
│   ├── 今日预测次数（实时）
│   └── 数据新鲜度（正常X只 / 待更新X只，红色预警）
│
├── 快捷入口（6个图标卡片，点击跳转对应页面）
│   智能预测 / 盘中估算 / 模型训练 / 多基金对比 / 基金画像 / 回测诊断
│
├── 主内容区（两列）
│   ├── 左列：最近预测列表
│   │   ├── 每行：基金名 + 预测涨跌 + 方向概率 + 置信度 + 是否已验证
│   │   └── "查看全部"链接
│   │
│   └── 右列：系统状态
│       ├── AI Provider 状态（GLM ✓ / SiliconFlow ✓）
│       ├── 数据更新状态（最后更新时间）
│       ├── 训练队列（当前排队X个任务）
│       └── "待重训模型"列表（如有，红色标注）
│
├── 准确率趋势图（折线图，近60日的方向准确率，ECharts）
│
└── 免责声明（小字灰色）
```

### 7.5 Predict 页面（`views/Predict.vue`）

**交互流程**：

```
Predict
├── 控制区
│   ├── FundCodeInput 组件（统一输入，含自动验证）
│   ├── 预测按钮（蓝色主按钮）
│   └── 高级选项折叠
│       └── 强制重训开关（默认关，仅高级用户使用）
│
├── [初始状态] 空态引导
│   └── 大图标 + "输入基金代码开始预测" + 最近预测历史入口
│
├── [加载中] 骨架屏（预测需要5-30s，分阶段提示进度）
│   ├── "获取数据中..."（0-3s）
│   ├── "构建特征中..."（3-5s）
│   ├── "模型推理中..."（5-8s）
│   └── "计算置信区间..."（8-10s）
│
├── [无模型错误] 内联提示
│   └── 黄色 Alert："该基金尚未训练模型"
│       + "前往训练"按钮（跳转 Train 页并预填代码）
│
├── [预测结果区]
│   ├── 基金信息头部
│   │   ├── 基金名称 + 类型标签
│   │   └── FundHealthCard（数据新鲜度 / 模型年龄 / 可靠性等级）
│   │
│   ├── 主结论卡（大号字体，视觉核心）
│   │   ├── 预测涨跌幅（+0.35%，绿色/红色）
│   │   ├── 置信区间条（[-0.82%, +1.52%]，可视化色带）
│   │   └── 置信度徽章（高/中/低，配色区分）
│   │
│   ├── 方向信号区（三列网格）
│   │   ├── 上涨概率（62%，仪表盘样式）
│   │   ├── 下跌概率（38%）
│   │   └── 净值区间预估（绝对值，如 1.87-1.90 元）
│   │
│   ├── 模型信息折叠区
│   │   ├── 使用模型：Stacking（Ridge + LGBM）
│   │   ├── 验证集 MAE：0.0041
│   │   ├── 方向准确率：64%
│   │   ├── Walk-Forward 轮数：9
│   │   └── 训练日期：2026-05-24
│   │
│   ├── SHAP 因子贡献（ShapPanel 组件）
│   │   ├── 标题："本次预测的主要驱动因子"
│   │   └── 水平条形图（正向绿/负向红，显示前5个）
│   │
│   ├── AI 一句话摘要（轻量版）
│   │   ├── "AI 认为：{summary 前80字}..."
│   │   └── "查看完整 AI 分析 →"（跳转或展开）
│   │
│   └── 免责声明
│
└── 特殊时期提示（如在季报窗口期，Banner 提醒）
```

### 7.6 Intraday 页面（`views/Intraday.vue`）

**核心特点**：盘中估算需要感知市场开收盘状态。

```
Intraday
├── 控制区
│   ├── FundCodeInput 组件
│   ├── 估算模式选择
│   │   ├── 自动（系统根据持仓时效自动选择）
│   │   ├── 持仓加权法（精度高，依赖季报数据）
│   │   └── 指数回归法（始终可用，精度略低）
│   ├── 开始估算按钮
│   └── 自动刷新开关（交易中时每 5 分钟刷新）
│
├── 市场状态横幅（MarketStatusBadge）
│   ├── [交易中] 绿色横幅："当前交易中（09:35 - 14:58）"
│   ├── [已收盘] 灰色横幅："今日已收盘（15:00），展示收盘前最后估算"
│   └── [非交易日] 灰色横幅："今日为非交易日，展示上一交易日估算"
│
├── 估算结果主卡
│   ├── 估算净值（大号数字）
│   ├── 估算涨跌幅（带颜色）
│   ├── 置信区间
│   ├── 估算方法标签（"持仓加权法"）
│   └── 上次刷新时间
│
├── 两列布局
│   ├── 左列：持仓贡献表格（HoldingsTable）
│   │   ├── 持仓时效警告标签（DataFreshnessTag）
│   │   │   "持仓数据：2026Q1 季报，距今42天 ⚠"
│   │   └── 表格：排名/股票/权重/今日涨跌/贡献度
│   │       （正贡献绿色/负贡献红色）
│   │
│   └── 右列：分项贡献分析
│       ├── 饼图/条形图展示各持仓股贡献占比
│       └── 与沪深300对比（今日超额/跑输）
│
├── 日内净值走势图（ECharts 折线，每次刷新追加一个点）
│
├── AI 解读区（AiAnalysisPanel，可折叠，默认展开）
│   ├── 标题 + Provider 标识 + 刷新按钮
│   ├── [加载中] 骨架屏（AI 异步加载，不阻塞主内容）
│   ├── 分析摘要文本
│   ├── 关键驱动因素列表
│   ├── 风险提示标签
│   ├── 操作建议徽章（ActionBadge）
│   └── 参考新闻来源（NewsSourceList）
│
└── 估算说明折叠区
    "本估算基于最新季报前十大持仓计算，实际净值以基金公司官方公布为准..."
```

### 7.7 Train 页面（`views/Train.vue`）

```
Train
├── 配置区
│   ├── FundCodeInput 组件
│   ├── 强制重训开关（含说明文字）
│   └── 开始训练按钮
│
├── [有进行中任务] 进度区
│   ├── 任务信息（ID / 基金名 / 状态 / 发起时间）
│   ├── 进度条（带阶段文字描述）
│   ├── 实时日志区（scrollable，新日志自动滚到底部）
│   └── 取消按钮
│
├── [训练完成] 结果卡
│   ├── 成功：✓ 训练完成 + 关键指标（MAE/准确率/模型版本）
│   │   └── "立即预测"按钮（带代码跳转 Predict 页）
│   └── 失败：✗ 训练失败 + 错误信息 + 重试按钮
│
└── 历史任务表格
    列：基金代码/名称 / 状态 / 发起时间 / 耗时 / MAE / 操作（查看日志）
    筛选：按状态/按日期
```

### 7.8 Profile 页面（`views/Profile.vue`）

```
Profile
├── URL 参数：/profile/110011（可从其他页面携带代码跳转）
│
├── 基金搜索区（FundCodeInput）
│
├── 基本信息卡片
│   ├── 基金名称（大号）+ 类型标签 + 评级
│   └── 六格指标网格：
│       代码 / 成立日期 / 最新规模
│       基金经理 / 基金公司 / 管理费率
│
├── 分类信息区（含置信度）
│   ├── 系统识别类型（如"偏股混合"）
│   ├── 分类置信度进度条
│   └── [置信度<0.7] 警告：用户可手动修正类型
│
├── 持仓信息（来自雪球季报）
│   ├── DataFreshnessTag 持仓时效标签
│   ├── 前十大持仓表格（权重/股票名/季报期）
│   └── 持仓集中度（CR10 = 前10持仓权重之和）
│
├── 图表区（两列）
│   ├── 左：资产配置饼图（股票/债券/现金）
│   └── 右：持仓行业分布条形图（申万一级行业）
│
├── 策略分析区
│   ├── 业绩比较基准
│   ├── 投资策略文本（可展开）
│   └── 提取的关键词标签（"成长""科技""医药"等）
│
├── 预测能力评估（如有训练记录）
│   ├── 模型版本 + 训练时间
│   ├── 近30日方向准确率
│   └── "前往预测"/ "重新训练"按钮
│
└── 数据状态区
    净值最新日期 / 数据总行数 / 持仓季报期
```

### 7.9 Backtest 页面（`views/Backtest.vue`）

```
Backtest
├── 控制区
│   ├── FundCodeInput 组件
│   ├── 时间范围（30天/60天/90天/180天/自定义）
│   └── 查询按钮
│
├── 指标卡片行（6卡）
│   ├── 方向准确率（64.5%）
│   ├── 平均绝对误差 MAE（0.0041）
│   ├── 均方根误差 RMSE（0.0058）
│   ├── 区间覆盖率80%（82.3%，目标>=80%）
│   ├── 区间覆盖率90%（90.3%，目标>=90%）
│   └── Spearman 相关系数（0.398）
│
├── 图表区（三块）
│   ├── 实际值 vs 预测值折线图
│   │   双轴：上方折线/下方误差带
│   │   切换：折线图 / 散点图
│   │
│   ├── 按市场状态的准确率雷达图
│   │   牛市 / 熊市 / 震荡市 各自的方向准确率
│   │
│   └── 误差分布直方图
│       横轴：预测误差大小，纵轴：频次
│
└── 详细数据表格（可下载 CSV）
    列：日期 / 预测涨跌 / 实际涨跌 / 误差 / 方向 / 是否在区间内
```

### 7.10 Compare 页面（`views/Compare.vue`）

```
Compare
├── 基金选择区
│   ├── 已选基金标签（可删除，最多10只）
│   ├── FundCodeInput（添加新基金）
│   └── 推荐快捷添加（来自最近使用）
│
├── 批量预测触发按钮（"预测全部"）
│
├── 对比结果区（有结果后显示）
│   ├── 汇总表格
│   │   列：基金名 / 类型 / 预测涨跌 / 置信区间 / 上涨概率 / 可信度 / 操作
│   │
│   ├── 预测涨跌对比条形图（水平条形，正负分列）
│   │
│   └── 基金详情卡片网格（每只基金一卡）
│       卡片内容：名称/类型/预测值/区间/建议操作
│       点击卡片跳转到该基金的完整预测页
│
└── 空态引导：添加至少2只基金开始对比
```

---

## 8. 前端组件详细设计

### 8.1 市场时间工具（`utils/marketTime.js`）

```javascript
// 判断当前是否在交易时段
export function getMarketSession() {
  const now = new Date()
  const day = now.getDay()  // 0=周日，6=周六
  
  // 周末不交易
  if (day === 0 || day === 6) {
    return { isTrading: false, session: 'weekend', note: '周末非交易日' }
  }
  
  const h = now.getHours()
  const m = now.getMinutes()
  const totalMinutes = h * 60 + m
  
  const openAuction  = 9 * 60 + 15   // 09:15 集合竞价
  const openContinuous = 9 * 60 + 30  // 09:30 连续竞价
  const noonClose    = 11 * 60 + 30   // 11:30 午间休市
  const afternoonOpen = 13 * 60       // 13:00 下午开盘
  const closeAuction = 14 * 60 + 57   // 14:57 尾盘集合竞价
  const marketClose  = 15 * 60        // 15:00 收盘
  
  if (totalMinutes >= openContinuous && totalMinutes < noonClose) {
    const remaining = noonClose - totalMinutes
    return { isTrading: true, session: 'morning', 
             note: `上午盘交易中（距午盘收市${remaining}分钟）` }
  }
  if (totalMinutes >= afternoonOpen && totalMinutes < closeAuction) {
    const remaining = marketClose - totalMinutes
    return { isTrading: true, session: 'afternoon', 
             note: `下午盘交易中（距收盘${remaining}分钟）` }
  }
  if (totalMinutes >= marketClose) {
    return { isTrading: false, session: 'closed', 
             note: `今日已收盘（15:00），展示收盘前最后估算` }
  }
  if (totalMinutes >= openAuction && totalMinutes < openContinuous) {
    return { isTrading: false, session: 'pre_open', note: '集合竞价中（09:15-09:30）' }
  }
  return { isTrading: false, session: 'pre_market', note: '盘前时段' }
}
```

### 8.2 AiAnalysisPanel 组件（`components/ai/AiAnalysisPanel.vue`）

```vue
<template>
  <el-card class="ai-analysis-panel">
    <template #header>
      <div class="panel-header">
        <span class="title">AI 解读</span>
        <el-tag v-if="analysisData" size="small" type="info">
          由 {{ analysisData.model_used }} 生成
        </el-tag>
        <el-button
          link size="small"
          :loading="loading"
          @click="refresh"
        >
          {{ loading ? '分析中...' : '刷新' }}
        </el-button>
      </div>
    </template>

    <!-- 加载骨架 -->
    <LoadingSkeleton v-if="loading" :lines="6" />

    <!-- 不可用状态 -->
    <el-empty v-else-if="unavailable" description="AI 分析暂时不可用">
      <template #description>
        <p>AI 服务暂时不可用，以下为参考新闻</p>
        <NewsSourceList :fund-code="fundCode" :news="fallbackNews" />
      </template>
    </el-empty>

    <!-- 分析结果 -->
    <div v-else-if="analysisData" class="analysis-content">
      <!-- 摘要 -->
      <p class="summary">{{ analysisData.analysis.summary }}</p>

      <!-- 关键驱动 -->
      <div class="key-drivers" v-if="analysisData.analysis.key_drivers.length">
        <div class="section-title">关键驱动</div>
        <div
          v-for="d in analysisData.analysis.key_drivers"
          :key="d.factor"
          class="driver-item"
          :class="d.direction === '正向' ? 'positive' : 'negative'"
        >
          <span class="icon">{{ d.direction === '正向' ? '↑' : '↓' }}</span>
          <span class="factor">{{ d.factor }}</span>
          <span class="desc">{{ d.desc }}</span>
        </div>
      </div>

      <!-- 风险提示 -->
      <div class="risk-factors" v-if="analysisData.analysis.risk_factors.length">
        <div class="section-title">风险提示</div>
        <el-tag
          v-for="r in analysisData.analysis.risk_factors"
          :key="r"
          type="warning"
          size="small"
          style="margin: 2px"
        >{{ r }}</el-tag>
      </div>

      <!-- 操作建议 -->
      <div class="suggested-action">
        <ActionBadge :action="analysisData.analysis.suggested_action" />
        <span class="reason">{{ analysisData.analysis.suggested_action_reason }}</span>
      </div>

      <!-- 新闻来源 -->
      <NewsSourceList
        v-if="analysisData.news_used.length"
        :news="analysisData.news_used"
        :fund-code="fundCode"
      />

      <!-- 免责声明 -->
      <p class="disclaimer">{{ analysisData.analysis.disclaimer }}</p>
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getAiAnalysis } from '@/api/ai'

const props = defineProps({
  fundCode: { type: String, required: true },
  context: { type: Object, default: () => ({}) },  // 包含 estimated_return 等
})

const loading = ref(false)
const analysisData = ref(null)
const unavailable = ref(false)
const fallbackNews = ref([])

async function fetchAnalysis(forceRefresh = false) {
  if (!props.fundCode) return
  loading.value = true
  unavailable.value = false
  try {
    analysisData.value = await getAiAnalysis({
      fund_code: props.fundCode,
      context: props.context,
      refresh: forceRefresh
    })
  } catch (err) {
    if (err.code === 'AI_PROVIDER_UNAVAILABLE') {
      unavailable.value = true
      fallbackNews.value = err.fallback?.news_items || []
    }
  } finally {
    loading.value = false
  }
}

function refresh() { fetchAnalysis(true) }

onMounted(() => fetchAnalysis())
watch(() => props.fundCode, () => fetchAnalysis())
</script>
```

### 8.3 DataFreshnessTag 组件（`components/common/DataFreshnessTag.vue`）

```vue
<template>
  <el-tag :type="tagType" size="small" class="freshness-tag">
    <el-icon><Clock /></el-icon>
    {{ label }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  daysSince: { type: Number, required: true },   // 距报告日期天数
  quarter: { type: String, default: '' },
  type: { type: String, default: 'holdings' }    // holdings / nav / model
})

const tagType = computed(() => {
  if (props.daysSince <= 30) return 'success'
  if (props.daysSince <= 60) return 'warning'
  return 'danger'
})

const label = computed(() => {
  const prefix = props.quarter ? `${props.quarter} ` : ''
  if (props.daysSince <= 30)
    return `${prefix}数据较新（${props.daysSince}天前）`
  if (props.daysSince <= 60)
    return `${prefix}数据适中（${props.daysSince}天前）⚠`
  return `${prefix}数据较旧（${props.daysSince}天前）需注意`
})
</script>
```

---

## 9. 配置文件

### 9.1 `config.yaml`

```yaml
# ==================================================
# 基金净值预测系统 · 全局配置
# ==================================================

app:
  name: "FundPredictor"
  version: "1.0.0"
  debug: false
  timezone: "Asia/Shanghai"

# ==================================================
# 数据层
# ==================================================
data:
  db_path: "data/fund_predictor.db"
  raw_dir: "data/raw"
  processed_dir: "data/processed"
  models_dir: "models"

  # 缓存
  nav_cache_ttl_seconds: 86400      # 基金净值内存缓存：当日有效
  nav_cache_maxsize: 500            # 最多缓存500只基金

  # AKShare 请求
  fetch_timeout_seconds: 20         # 单次请求超时
  fetch_max_workers: 5              # 并发获取线程数
  fetch_retry_times: 2              # 失败重试次数

  # 数据最小要求
  min_train_rows: 220               # 最小训练样本数（交易日）
  cold_start_threshold: 250         # 低于此天数使用群体模型（修复120-220盲区）

# ==================================================
# 特征工程
# ==================================================
feature:
  lookback_lags: [1, 2, 3, 5, 10]
  rolling_windows: [5, 10, 20, 60]
  beta_window: 20
  volatility_window: 20
  style_window: 60

# ==================================================
# 因子筛选
# ==================================================
screening:
  ic_threshold: 0.02          # 改为 Spearman IC 阈值
  use_spearman: true          # 修复原文档使用 Pearson 的问题
  vif_threshold: 10.0
  icir_threshold: 0.5
  vif_method: "cluster"       # cluster（基于相关性聚类，修复路径依赖问题）
  cluster_corr_threshold: 0.8 # 相关系数>0.8视为同一簇

# ==================================================
# 模型训练（动态参数，修复WF-CV失配问题）
# ==================================================
model:
  # 四段划分（保护 Test_final 不被 WF-CV 触碰）
  train_split_ratio: [0.55, 0.22, 0.13, 0.10]

  # Walk-Forward CV（动态参数）
  wfcv_dynamic: true              # 根据数据量动态计算训练窗口
  wfcv_max_train_months: 24       # 最大训练窗口（月）
  wfcv_min_rounds: 3              # 最小轮数（低于此降级为 Hold-out）
  wfcv_step_months: 1

  # 模型选择：联合指标（修复只看MAE的问题）
  selection_mae_weight: 0.60
  selection_direction_weight: 0.40
  direction_accuracy_min: 0.52    # 方向准确率最低门槛

  # 样本权重
  sample_weight_halflife: 60

  # 候选模型
  candidate_models:
    - name: "ridge"
      alpha: 1.0
    - name: "elasticnet"
      alpha: 0.01
      l1_ratio: 0.5
    - name: "lgbm"
      n_estimators: 120
      max_depth: 5
      learning_rate: 0.05
      min_child_samples: 10
    - name: "xgboost"
      n_estimators: 120
      max_depth: 5
      learning_rate: 0.05

  # 模型版本保留数
  keep_versions: 3

# ==================================================
# 保形预测
# ==================================================
interval:
  default_alpha: 0.10           # 90% 置信区间
  # 校准集：明确使用 Test_select（13%段），不用 Valid 集
  calibration_split: "test_select"

# ==================================================
# 净值约束
# ==================================================
nav_constraints:
  hybrid_equity:    0.20
  equity_active:    0.20
  hybrid_balanced:  0.15
  hybrid_bond:      0.10
  hybrid_flexible:  0.20
  bond_pure:        0.05
  bond_mixed:       0.08
  bond_convertible: 0.20
  index_equity:     null
  index_bond:       null
  fof:              0.15
  qdii:             0.20

# ==================================================
# 债券先验
# ==================================================
bond:
  duration_estimate:
    bond_pure:        3.0
    bond_mixed:       2.5
    bond_convertible: 1.5
  daily_fee: 0.000003

# ==================================================
# 冷启动（修复120-220天盲区）
# ==================================================
cold_start:
  threshold_days: 250             # 统一阈值，覆盖220+30天余量
  blend_start_days: 250           # 开始过渡
  blend_end_days: 400             # 完全切换到个体模型
  min_peers: 3                    # 群体模型最少同类基金数

# ==================================================
# AI 分析
# ==================================================
ai_provider:
  primary:
    provider: "glm"
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4-flash"
    timeout_seconds: 8            # 缩短至8s（原来15s太长）
    max_tokens: 512
    temperature: 0.3

  fallback:
    provider: "siliconflow"
    base_url: "https://api.siliconflow.cn/v1"
    model: "Qwen/Qwen2.5-7B-Instruct"
    timeout_seconds: 12
    max_tokens: 512
    temperature: 0.3

  # 并发策略（解决串行超时过长问题）
  concurrent_providers: true      # 主备并发，谁先返回用谁
  total_timeout_seconds: 10       # 并发总超时
  retry_times: 1                  # 重试1次（不是2次，避免过长等待）
  cache_ttl: "day"
  allowed_actions: ["增持", "持有", "减持", "观望"]
  force_json_output: true         # 同时配合 API 的 response_format 参数

# ==================================================
# 新闻聚合
# ==================================================
news_service:
  sources:
    cls:
      enabled: true
      max_items: 50
      relevance_min_score: 0.3
    em:
      enabled: true
      max_items: 20
      relevance_min_score: 0.4
      # 注意：直接用重仓股代码查询，不用基金代码
      use_holdings_codes: true
      max_holdings_to_query: 5    # 最多查5只重仓股的新闻

  max_news_for_ai: 3
  max_news_for_display: 5
  cache_minutes: 10
  fetch_timeout_seconds: 8
  news_max_age_hours: 36          # 超过36小时的新闻不使用

# ==================================================
# 任务队列
# ==================================================
task:
  max_concurrent: 2               # 最大并发训练任务（降为2，避免SQLite竞争）
  task_timeout_seconds: 300       # 单个训练任务最大耗时

# ==================================================
# API
# ==================================================
api:
  version: "v1"
  request_timeout: 30
  rate_limit:
    ai_refresh_per_fund_minutes: 30   # 同一基金AI刷新最短间隔
    batch_predict_max: 10             # 批量预测最多10只

# ==================================================
# 调度任务
# ==================================================
scheduler:
  nav_update_time: "17:30"        # 每日净值更新
  backfill_time: "21:30"          # 每日回填预测误差
  model_health_check_day: "sat"   # 每周六模型健康检查
  model_health_check_time: "08:00"

# ==================================================
# 日志
# ==================================================
logging:
  level: "INFO"
  dir: "logs"
  handlers:
    app:   { filename: "app.log",    max_bytes: 10485760, backup_count: 30 }
    api:   { filename: "api.jsonl",  format: "json" }
    train: { filename: "train.log",  level: "DEBUG" }
    error: { filename: "error.log",  level: "ERROR" }
    audit: { filename: "audit.jsonl",format: "json" }
    perf:  { filename: "perf.jsonl", format: "json" }
```

### 9.2 `.env.example`

```bash
# 复制此文件为 .env 并填写实际值

# ==================================================
# AI Provider API Keys（必填，否则 AI 分析功能不可用）
# ==================================================
# 智谱 GLM：https://open.bigmodel.cn/usercenter/apikeys
GLM_API_KEY=your_glm_api_key_here

# 硅基流动：https://cloud.siliconflow.cn/account/ak
SILICONFLOW_API_KEY=your_siliconflow_api_key_here

# ==================================================
# 应用配置
# ==================================================
APP_ENV=production              # development / production
SECRET_KEY=change_this_to_random_string

# ==================================================
# 前端配置（Vite 构建时注入）
# ==================================================
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=基金净值预测系统
```

### 9.3 `requirements.txt`

```
# 核心框架
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9

# 数据库
sqlalchemy==2.0.36
aiosqlite==0.20.0

# 数据获取
akshare==1.15.0             # 版本建议固定，API 变动频繁
httpx==0.27.0               # AI Provider 异步调用
requests==2.32.0            # 新浪实时行情同步调用

# 数据处理
pandas==2.2.0
numpy==1.26.0
scipy==1.13.0

# 机器学习
scikit-learn==1.5.0
lightgbm==4.4.0
xgboost==2.1.0
joblib==1.4.0
shap==0.45.0                # SHAP 因子解释

# 缓存
cachetools==5.4.0           # 线程安全 TTLCache（替换全局 dict）

# 任务调度
apscheduler==3.10.4

# 配置
pyyaml==6.0.2
python-dotenv==1.0.1        # 读取 .env 文件

# 日志
structlog==24.4.0

# 工具
pydantic==2.8.0
```

### 9.4 `package.json`（前端）

```json
{
  "name": "fund-predictor-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "element-plus": "^2.7.0",
    "@element-plus/icons-vue": "^2.3.0",
    "axios": "^1.7.0",
    "echarts": "^5.5.0",
    "vue-echarts": "^7.0.0",
    "dayjs": "^1.11.0",
    "sass": "^1.77.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vite": "^5.3.0",
    "unplugin-auto-import": "^0.18.0",
    "unplugin-vue-components": "^0.27.0"
  }
}
```

### 9.5 `vite.config.js`

```javascript
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  return {
    plugins: [
      vue(),
      AutoImport({ resolvers: [ElementPlusResolver()] }),
      Components({ resolvers: [ElementPlusResolver()] }),
    ],
    resolve: {
      alias: { '@': resolve(__dirname, 'src') }
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000',
          changeOrigin: true,
        }
      }
    }
  }
})
```

---

## 10. 启动与部署

### 10.1 本地开发启动

```bash
# 1. 克隆项目并安装依赖
cd fund_predictor
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 GLM_API_KEY 和 SILICONFLOW_API_KEY

# 3. 初始化数据库（首次运行）
cd backend
python -m app.core.database init

# 4. 启动后端（开发模式，热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. 前端（新终端）
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

### 10.2 `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

# frontend Dockerfile 使用 nginx 托管 dist
# 并配置 /api 反向代理到 backend:8000
```

### 10.3 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（lightgbm 需要 libgomp）
RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据目录
RUN mkdir -p data/raw/fund_nav data/raw/holdings data/raw/index \
             data/processed models logs

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.4 首次使用流程

```
1. 部署并启动系统
   ↓
2. 打开浏览器访问 http://localhost（或开发时的 3000）
   ↓
3. 前往"数据管理"页面
   点击"全量更新"拉取指数历史数据（约1-2分钟）
   ↓
4. 在"基金画像"页输入想要预测的基金代码
   确认分类正确后保存
   ↓
5. 前往"模型训练"页
   输入基金代码，点击"开始训练"
   等待训练完成（约30秒-3分钟，取决于数据量）
   ↓
6. 前往"智能预测"页
   输入同一基金代码，点击"预测"
   查看 T+1 预测结果和 AI 分析
   ↓
7. 交易时间内前往"T日盘中估算"
   实时查看当日净值估算
```

---

## 附录：关键设计决策汇总

| 决策点 | 方案 | 原因 |
|---|---|---|
| 基金代码输入 | 统一 FundCodeInput 组件 | 6个页面共用，容错逻辑只写一次 |
| NAV 缓存 | TTLCache + RLock | 解决原 dict 线程安全问题 |
| WF-CV 参数 | 动态计算，不固定24个月 | 修复原文档与 MIN_TRAIN_ROWS 失配 |
| 冷启动阈值 | 统一为250天 | 消除120-220天无处理的盲区 |
| 因子筛选 | Spearman IC + 聚类去重 | 比 Pearson 更鲁棒，消除路径依赖 |
| 模型选择 | MAE×0.6 + 方向准确率×0.4 | 纯 MAE 可能选出方向预测差的模型 |
| 保形预测校准集 | 明确使用 Test_select 段 | 避免 Valid 集复用导致区间偏窄 |
| AI 调用策略 | 主备并发，10s总超时 | 避免串行最坏110s等待 |
| AI JSON 输出 | Prompt + response_format 双重保证 | 比纯 Prompt 可靠 |
| 持仓映射接口 | 新浪实时行情（直接HTTP） | 比 AKShare 封装更快，延迟<500ms |
| 新闻查询 | 用重仓股代码查东财 | stock_news_em 不支持基金代码 |
| 模型版本 | 按日期命名保留3个版本 | 支持快速回滚 |
| 数据更新 | APScheduler 17:30 自动拉取 | 解决原文档无调度机制问题 |
| AI 刷新限流 | 同基金30分钟最多1次 | 防止用户频繁点刷新耗尽配额 |
| 投资建议免责 | 固定字段强制输出 | 法律合规必要项 |

---

*文档版本：v1.0 | 生成于 2026-05-26*
