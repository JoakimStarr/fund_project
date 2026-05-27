# 基金 T+1 净值涨跌幅区间预测系统 — 技术文档

> 版本: v2.6.0 | 更新: 2026-05-26
> 本文档在 v2.5.4 基础上增量更新，新增 AI 分析与新闻聚合模块。
> 变更章节已标注 `[MODIFIED]`，新增章节标注 `[NEW]`，未变更章节保持原样。

---

## 变更日志（v2.5.4 → v2.6.0）

| 变更类型 | 章节 | 内容摘要 |
|---|---|---|
| MODIFIED | §1 系统架构总览 | 架构图新增 AI 分析层、新闻聚合层 |
| MODIFIED | §2 目录结构 | 新增 `ai_analysis_service.py`、`news_service.py`、`ai_prompt_templates/` |
| MODIFIED | §12 API 接口规范 | 新增 3 个 AI 分析相关接口 |
| MODIFIED | §13 配置参数手册 | 新增 `ai_provider` 配置块 |
| MODIFIED | §14 前端架构 | Intraday/Predict 页面新增 AI 解读区域 |
| NEW | §16 新闻聚合模块 | AKShare 多源新闻获取、相关性过滤 |
| NEW | §17 AI 分析服务 | 智谱 GLM / 硅基流动双 Provider、Prompt 模板体系 |
| NEW | 附录C | AI Provider 接口规范与错误码 |

---

## 目录

1. [系统架构总览](#1-系统架构总览) `[MODIFIED]`
2. [目录结构与模块依赖](#2-目录结构与模块依赖) `[MODIFIED]`
3. [端到端数据流](#3-端到端数据流)
4. [基金分类路由系统](#4-基金分类路由系统)
5. [数据获取层](#5-数据获取层)
6. [特征工程](#6-特征工程)
7. [因子预筛选](#7-因子预筛选)
8. [模型训练与选择](#8-模型训练与选择)
9. [集成学习（Stacking）](#9-集成学习stacking)
10. [后处理：保形预测与净值约束](#10-后处理保形预测与净值约束)
11. [冷启动机制](#11-冷启动机制)
12. [API 接口规范](#12-api-接口规范) `[MODIFIED]`
13. [配置参数手册](#13-配置参数手册) `[MODIFIED]`
14. [前端架构](#14-前端架构) `[MODIFIED]`
15. [日志系统](#15-日志系统)
16. [新闻聚合模块](#16-新闻聚合模块) `[NEW]`
17. [AI 分析服务](#17-ai-分析服务) `[NEW]`
18. [附录A: 异常处理全景](#附录a-异常处理全景)
19. [附录B: 性能关键路径](#附录b-性能关键路径)
20. [附录C: AI Provider 接口规范](#附录c-ai-provider-接口规范) `[NEW]`

---

## 1. 系统架构总览 `[MODIFIED]`

```
┌──────────────────────────────────────────────────────────────────┐
│                      前端 (Vue3 + Vite)                           │
│  Predict / Train / Backtest / Dashboard / Intraday / ...         │
│                                                                  │
│  ★ Intraday 新增: AI解读折叠区 / 新闻来源列表 / 持仓时效警告      │
│  ★ Predict 新增: 因子贡献 SHAP 展示 / AI摘要                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP (axios, baseURL=/api/v1)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI 后端                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Fund API │  │ Train API│  │ Task API │  │ AI Analysis API│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
│       │              │              │                │           │
│       ▼              ▼              ▼                ▼           │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              Routing Service (路由引擎)                  │     │
│  │  classify_fund() → fund_type → pipeline                 │     │
│  └──────────────────────┬─────────────────────────────────┘     │
│                         ▼                                        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │            Prediction Service (预测核心)                 │     │
│  │  数据获取 → 特征构建 → 因子筛选 → 模型训练               │     │
│  │       → Stacking集成 → 保形区间 → 净值约束               │     │
│  └────────────────────────────────────────────────────────┘     │
│                         │                                        │
│  ┌──────────────────────┴─────────────────────────────────┐     │
│  │  Cold Start | Intraday | FOF | Hyperopt | Cache         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ★ 新增服务层                                                     │
│  ┌─────────────────────────┐  ┌──────────────────────────┐      │
│  │   News Service          │  │   AI Analysis Service    │      │
│  │ ┌─────────────────────┐ │  │ ┌──────────────────────┐ │      │
│  │ │ 财联社电报(AKShare)  │ │  │ │ Provider Router      │ │      │
│  │ │ 东方财富个股新闻     │ │  │ │ ┌──────┐ ┌────────┐  │ │      │
│  │ │ 新浪财经快讯         │ │  │ │ │ GLM  │ │Silicon │  │ │      │
│  │ │ 相关性过滤器         │ │  │ │ │(智谱)│ │  Flow  │  │ │      │
│  │ └─────────────────────┘ │  │ └──────┘ └────────┘  │ │      │
│  └─────────────────────────┘  │ Prompt Template Engine  │ │      │
│                                │ └──────────────────────┘ │      │
│                                └──────────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                      数据存储层                                    │
│  SQLite (WAL) │ CSV (raw/processed) │ Joblib (.pkl)               │
│  ★ 新增: ai_analysis_cache 表 (分析结果缓存，TTL=当日有效)         │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                      外部 AI API                                  │
│  智谱 GLM API (api.bigmodel.cn)  │  硅基流动 (api.siliconflow.cn) │
└──────────────────────────────────────────────────────────────────┘
```

### 技术栈（更新）

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn (Python 3.11+) |
| 前端框架 | Vue 3 + Vite + Element Plus + ECharts |
| 数据存储 | SQLite WAL模式 + CSV文件 + Joblib模型序列化 |
| 机器学习 | scikit-learn + Ridge/ElasticNet/LGBM/XGBoost |
| 统计方法 | Conformal Prediction, Walk-Forward CV |
| **新闻聚合** | **AKShare 多接口（财联社/东方财富/新浪财经）** |
| **AI 推理** | **智谱 GLM API / 硅基流动 API（OpenAI 兼容格式）** |
| 部署 | Docker Compose (backend + nginx frontend) |

---

## 2. 目录结构与模块依赖 `[MODIFIED]`

```
fund_predictor/
├── config.yaml                    # 全局配置（新增 ai_provider 配置块）
├── backend/app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   ├── errors.py              # ★ 新增: AIProviderError, NewsServiceError
│   │   ├── perf_logger.py
│   │   └── audit_logger.py
│   ├── api/
│   │   ├── fund.py
│   │   ├── train.py
│   │   ├── task.py
│   │   ├── model.py
│   │   ├── backtest.py
│   │   ├── intraday.py
│   │   ├── dashboard.py
│   │   └── ai_analysis.py         # ★ 新增: AI 分析接口（3个端点）
│   ├── services/
│   │   ├── routing_service.py
│   │   ├── prediction_service.py
│   │   ├── data_service.py
│   │   ├── feature_service.py
│   │   ├── model_selection_service.py
│   │   ├── task_service.py
│   │   ├── fund_profile_service.py
│   │   ├── cold_start.py
│   │   ├── news_service.py        # ★ 新增: AKShare 多源新闻聚合
│   │   ├── ai_analysis_service.py # ★ 新增: Provider路由 + 调用封装
│   │   ├── ai_prompt_templates/   # ★ 新增: 按基金类型分类的 Prompt 模板
│   │   │   ├── __init__.py
│   │   │   ├── equity_template.py    # 偏股/主动股票型
│   │   │   ├── bond_template.py      # 债券型（利率/信用利差导向）
│   │   │   ├── index_template.py     # 指数/ETF型
│   │   │   ├── mixed_template.py     # 平衡/灵活混合型
│   │   │   └── base_template.py      # 通用基础模板（其他类型）
│   │   ├── features/
│   │   │   ├── factor_screening.py
│   │   │   ├── ensemble.py
│   │   │   ├── enhanced_equity_features.py
│   │   │   ├── bond_features.py
│   │   │   └── macro_features.py
│   │   ├── postprocessing/
│   │   │   ├── conformal.py
│   │   │   └── constraints.py
│   │   ├── pipelines/
│   │   │   └── flexible_pipeline.py
│   │   └── rules/
│   │       └── index_rule_engine.py
│   └── db/
│       ├── database.py
│       └── models.py              # ★ 新增: AIAnalysisCache ORM 模型
├── frontend/src/
│   ├── api/
│   │   └── ai_analysis.js         # ★ 新增: AI 分析 API 调用模块
│   ├── views/
│   │   ├── Intraday.vue           # ★ 修改: 新增 AI 解读折叠区
│   │   ├── Predict.vue            # ★ 修改: 新增因子贡献 + AI摘要
│   │   └── ...                    # 其余页面不变
│   ├── components/
│   │   ├── AiAnalysisPanel.vue    # ★ 新增: AI 分析展示公共组件
│   │   └── NewsSourceList.vue     # ★ 新增: 新闻来源列表公共组件
│   └── ...
├── data/raw/
├── data/processed/
├── models/{fund_code}/
├── logs/
└── tests/
    └── test_ai_analysis.py        # ★ 新增: AI 分析模块单元测试
```

### 模块依赖图（更新）

```
main.py
  ├─> routing_service.py
  │     └─> fund_profile_service.py
  │           └─> data_service.py
  ├─> prediction_service.py
  │     ├─> data_service.py
  │     ├─> feature_service.py
  │     │     ├─> enhanced_equity_features.py
  │     │     ├─> bond_features.py
  │     │     └─> macro_features.py
  │     ├─> factor_screening.py
  │     ├─> model_selection_service.py
  │     │     └─> ensemble.py
  │     ├─> conformal.py
  │     └─> constraints.py
  ├─> cold_start.py
  ├─> intraday_service.py
  │
  ├─> ★ news_service.py            (新增，被 ai_analysis_service 调用)
  │     ├─> akshare.stock_telegraph_cls_em()   财联社电报
  │     ├─> akshare.stock_news_em()            东方财富个股新闻
  │     └─> akshare.stock_news_sina()          新浪财经快讯
  │
  └─> ★ ai_analysis_service.py     (新增，被 ai_analysis.py API 调用)
        ├─> news_service.py
        ├─> fund_profile_service.py
        ├─> ai_prompt_templates/
        └─> AI Provider (GLM / SiliconFlow HTTP Client)
```

---

## 3–11. （内容与 v2.5.4 保持一致，此处略）

> 第 3 章至第 11 章内容不变，请参照 v2.5.4 原文档。

---

## 12. API 接口规范 `[MODIFIED]`

### 12.1 接口清单（更新）

| 方法 | 路径 | 功能 | 认证 |
|-----|------|------|------|
| POST | `/api/v1/fund/predict` | 发起基金预测 | 无 |
| GET | `/api/v1/fund/{code}/profile` | 获取基金画像 | 无 |
| GET | `/api/v1/fund/{code}/model` | 获取已训练模型信息 | 无 |
| GET | `/api/v1/fund/{code}/backtest` | 获取回测结果 | 无 |
| POST | `/api/v1/train` | 创建训练任务 | 无 |
| GET | `/api/v1/tasks` | 任务列表 | 无 |
| GET | `/api/v1/tasks/{id}` | 任务详情/状态 | 无 |
| POST | `/api/v1/intraday/{code}` | T日日内估计 | 无 |
| GET | `/api/v1/intraday/{code}/latest` | 最新日内估计 | 无 |
| GET | `/api/v1/model/health` | 模型服务健康检查 | 无 |
| GET | `/api/v1/backtest/health` | 回测服务健康检查 | 无 |
| GET | `/api/v1/dashboard/stats` | 仪表盘统计数据 | 无 |
| GET | `/api/v1/dashboard/recent-predictions` | 最近预测记录 | 无 |
| GET | `/api/v1/dashboard/models` | 已训练模型列表 | 无 |
| **GET** | **`/api/v1/fund/{code}/ai-analysis`** | **★ 获取AI分析（含新闻）** | **无** |
| **GET** | **`/api/v1/fund/{code}/news`** | **★ 获取基金相关新闻列表** | **无** |
| **GET** | **`/api/v1/ai/provider-status`** | **★ AI Provider 可用性检测** | **无** |

---

### 12.2 预测接口（原有，结构不变）

（内容与 v2.5.4 保持一致，略）

---

### 12.3 ★ AI 分析接口详情（新增）

#### `GET /api/v1/fund/{code}/ai-analysis`

在已有的 Intraday 或 Predict 结果基础上，异步调用 AI Provider 生成自然语言分析报告。

**查询参数**:

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `estimation_return` | float | 必填 | 当前盘中/T+1预测收益率（来自估算或预测结果） |
| `lower_bound` | float | 必填 | 置信区间下界 |
| `upper_bound` | float | 必填 | 置信区间上界 |
| `source` | string | `"intraday"` | 分析来源，`intraday` 或 `predict` |
| `refresh` | bool | `false` | 是否强制刷新（忽略当日缓存） |

**调用流程（内部）**:

```
接收请求
  │
  ├─ 1. 检查当日缓存 (ai_analysis_cache 表)
  │       IF 缓存存在 AND refresh=false AND 缓存时间在当日 → 直接返回缓存
  │
  ├─ 2. 并发执行（两个独立任务同时启动）
  │       ├─ Task A: news_service.fetch_relevant_news(code)       ~1-3s
  │       └─ Task B: fund_profile_service.get_holdings(code)      ~0.5s
  │
  ├─ 3. 根据基金类型选择 Prompt 模板
  │       fund_type → ai_prompt_templates/{type}_template.py
  │
  ├─ 4. 组装 Prompt（见 §17.3）
  │
  ├─ 5. 调用 AI Provider（见 §17.2）
  │       主 Provider → 备用 Provider（失败时自动切换）
  │
  ├─ 6. 解析 AI 输出（JSON 结构化）
  │
  ├─ 7. 写入 ai_analysis_cache 表
  │
  └─ 返回结果
```

**成功响应** (200):

```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "fund_name": "易方达中小盘混合",
    "fund_type": "equity_active",
    "analysis": {
      "summary": "今日沪深300受科技板块拖累小幅下行，但本基金前十大重仓中医药与消费标的表现相对抗跌，预计净值跌幅小于大盘。利率维持稳定，对持仓中的债性资产无明显冲击。",
      "key_drivers": [
        { "factor": "医药板块", "direction": "正向", "desc": "CXO龙头股今日逆势上涨约1.2%" },
        { "factor": "沪深300指数", "direction": "负向", "desc": "大盘跌0.8%，对重仓股形成压制" }
      ],
      "risk_factors": [
        "美联储议息会议结果今晚公布，存在海外扰动",
        "北向资金今日净流出30亿，外资情绪偏谨慎"
      ],
      "suggested_action": "持有",
      "suggested_action_reason": "估算跌幅有限，主题逻辑未变，建议持有观察"
    },
    "news_used": [
      {
        "title": "CXO板块集体上涨，药明康德涨超2%",
        "source": "财联社",
        "time": "2026-05-26 10:23",
        "relevance_score": 0.92
      },
      {
        "title": "北向资金早盘净流出约28亿",
        "source": "东方财富",
        "time": "2026-05-26 10:45",
        "relevance_score": 0.78
      }
    ],
    "holdings_data_info": {
      "quarter": "2026Q1",
      "days_since_report": 42,
      "freshness_level": "medium",
      "freshness_warning": "持仓数据来源：2026年Q1季报，距今42天，准确性适中"
    },
    "provider_used": "glm",
    "model_used": "glm-4-flash",
    "cached": false,
    "generated_at": "2026-05-26T10:52:33Z"
  }
}
```

**错误响应**（AI Provider 不可用时降级）:

```json
{
  "ok": false,
  "error": {
    "code": "AI_PROVIDER_UNAVAILABLE",
    "message": "所有 AI Provider 当前不可用，请稍后重试",
    "status": 503,
    "fallback": {
      "news_only": true,
      "news_items": [...]
    }
  }
}
```

---

#### `GET /api/v1/fund/{code}/news`

仅获取新闻列表，不调用 AI，响应更快（约 1-3s）。

**查询参数**:

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | `5` | 返回新闻条数（最多 10） |
| `source` | string | `"all"` | 新闻来源：`cls`（财联社）/ `em`（东方财富）/ `all` |

**成功响应** (200):

```json
{
  "ok": true,
  "data": {
    "fund_code": "110011",
    "news": [
      {
        "title": "CXO板块集体上涨，药明康德涨超2%",
        "content": "受海外订单回暖预期影响...",
        "source": "财联社",
        "source_type": "cls",
        "url": "https://...",
        "published_at": "2026-05-26T10:23:00Z",
        "relevance_score": 0.92,
        "matched_keywords": ["药明康德", "CXO"]
      }
    ],
    "total": 3,
    "fetched_at": "2026-05-26T10:52:00Z"
  }
}
```

---

#### `GET /api/v1/ai/provider-status`

检测当前配置的 AI Provider 可用性，用于前端展示状态和 AdminDataStatus 页面。

**成功响应** (200):

```json
{
  "ok": true,
  "data": {
    "primary": {
      "provider": "glm",
      "model": "glm-4-flash",
      "status": "available",
      "latency_ms": 234,
      "last_checked": "2026-05-26T10:50:00Z"
    },
    "fallback": {
      "provider": "siliconflow",
      "model": "Qwen/Qwen2.5-7B-Instruct",
      "status": "available",
      "latency_ms": 412,
      "last_checked": "2026-05-26T10:50:00Z"
    }
  }
}
```

---

## 13. 配置参数手册 `[MODIFIED]`

### 13.1 config.yaml（新增 `ai_provider` 块）

以下为新增配置块，追加至原 `config.yaml` 末尾。原有配置全部保持不变。

```yaml
# ====================================================
# ★ AI 分析模块配置（v2.6.0 新增）
# ====================================================

ai_provider:

  # --- 主 Provider ---
  primary:
    provider: "glm"                  # 可选: "glm" | "siliconflow"
    api_key: "${GLM_API_KEY}"        # 从环境变量读取，禁止硬编码
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4-flash"            # 推荐: glm-4-flash（快速、成本低）
                                    # 备选: glm-4-air（更强，成本略高）
    timeout_seconds: 15             # 单次请求超时（AI推理通常3-8s）
    max_tokens: 512                 # 限制输出长度（分析报告150字够用）
    temperature: 0.3                # 低随机性，保证输出稳定可解析

  # --- 备用 Provider（主 Provider 失败时自动切换）---
  fallback:
    provider: "siliconflow"
    api_key: "${SILICONFLOW_API_KEY}"
    base_url: "https://api.siliconflow.cn/v1"
    model: "Qwen/Qwen2.5-7B-Instruct"  # 推荐: 免费额度充足
                                        # 备选: "deepseek-ai/DeepSeek-V2.5"
    timeout_seconds: 20
    max_tokens: 512
    temperature: 0.3

  # --- 调用策略 ---
  retry_times: 2                   # 同一 Provider 的重试次数
  retry_delay_seconds: 1           # 重试等待时间
  fallback_on_error: true          # 主 Provider 失败时是否切换备用
  cache_ttl: "day"                 # 缓存有效期: "day"=当日有效（次日清除）

  # --- 输出格式约束 ---
  force_json_output: true          # 强制要求 AI 输出 JSON（Prompt 中硬约束）
  allowed_actions:                 # suggested_action 枚举白名单
    - "增持"
    - "持有"
    - "减持"
    - "观望"

# ====================================================
# ★ 新闻聚合配置（v2.6.0 新增）
# ====================================================

news_service:

  # --- AKShare 新闻源配置 ---
  sources:
    cls:                           # 财联社电报
      enabled: true
      akshare_func: "stock_telegraph_cls_em"
      max_items: 50                # 每次拉取条数
      relevance_min_score: 0.3     # 最低相关性分数（0-1）
    em:                            # 东方财富个股新闻
      enabled: true
      akshare_func: "stock_news_em"
      max_items: 20
      relevance_min_score: 0.4
    sina:                          # 新浪财经快讯
      enabled: false               # 默认关闭（数据质量较低）
      akshare_func: "stock_news_sina"
      max_items: 20
      relevance_min_score: 0.5

  # --- 相关性计算 ---
  keyword_sources:
    - "fund_name"                  # 基金名称关键词
    - "top5_holdings"              # 前5大重仓股名称
    - "fund_type_keywords"         # 基金类型关键词（如"医药""科技"）
  max_news_for_ai: 3               # 送入 AI 的最大新闻条数
  max_news_for_display: 5          # 前端展示的最大条数

  # --- 缓存 ---
  cache_minutes: 10                # 新闻列表缓存（分钟），盘中频繁访问时避免重复拉取
  fetch_timeout_seconds: 8         # 单次 AKShare 新闻请求超时
```

### 13.2 环境变量配置（`.env` 文件，新增）

```bash
# .env（项目根目录，不提交至版本控制）

# 智谱 GLM API Key
# 获取地址: https://open.bigmodel.cn/usercenter/apikeys
GLM_API_KEY=your_glm_api_key_here

# 硅基流动 API Key
# 获取地址: https://cloud.siliconflow.cn/account/ak
SILICONFLOW_API_KEY=your_siliconflow_api_key_here
```

**安全要求**:

- `.env` 文件必须加入 `.gitignore`，禁止提交至任何版本控制系统；
- Docker 部署时通过 `docker-compose.yml` 的 `env_file` 字段注入，不在镜像层固化；
- 代码中通过 `os.environ.get("GLM_API_KEY")` 读取，配置加载器在启动时校验 Key 非空，否则将 AI 功能标记为 `disabled`，系统其他功能正常运行。

---

## 14. 前端架构 `[MODIFIED]`

### 14.1 技术栈（不变）

（内容与 v2.5.4 保持一致，略）

### 14.2 页面路由（不变）

（内容与 v2.5.4 保持一致，略）

### 14.3 ★ Intraday 页面变更（新增 AI 解读区）

原有结构在**结果区**末尾追加 `AiAnalysisPanel` 组件：

```
结果区（原有，保持不变）
├── 主要估值卡片（估算净值、涨跌、置信度）
├── 详细数据网格
│   ├── 重仓股贡献表格        ← ★ 新增: 持仓时效警告标签
│   │     "持仓数据：2026Q1季报，距今42天 ⚠"
│   └── 分项贡献分析图
├── 日内净值估算走势图
│
└── ★ 新增: AI 解读区（可折叠，默认展开）
    ├── 标题栏
    │   ├── "AI 解读"标题
    │   ├── Provider标识（"由 GLM-4-Flash 生成"）
    │   └── 刷新按钮（强制重新生成，绕过缓存）
    │
    ├── 加载状态（骨架屏，3-8秒）
    │
    ├── 分析摘要文本（150字以内）
    │
    ├── 关键驱动因素列表（图标+文字，正向绿色/负向红色）
    │
    ├── 风险提示（橙色背景标签列表）
    │
    ├── 操作建议（大字徽章：增持/持有/减持/观望）
    │   └── 建议理由（小字说明）
    │
    └── 参考新闻来源（NewsSourceList 组件）
        ├── 新闻标题（可点击，新标签页打开）
        ├── 来源（财联社/东方财富）
        ├── 发布时间
        └── 相关性分数（进度条样式）
```

**交互细节**:

- AI 解读区与估算结果分离加载：估算净值立即展示，AI 解读异步请求（用户不需等待 AI 才能看到核心数据）；
- 若 AI Provider 不可用，解读区显示"AI 分析暂时不可用"灰色提示，不影响主功能；
- 持仓数据时效警告颜色规则：
  - 0–30 天：绿色标签"数据较新"；
  - 31–60 天：黄色警告"数据适中"；
  - 60 天以上：橙色警告"数据较旧，准确性降低"。

### 14.4 ★ Predict 页面变更（新增 AI 摘要）

原有结构在**关键可信度指标**之后追加 AI 简短摘要入口：

```
结果区（原有，保持不变）
├── 主结论卡
├── 方向信号网格
├── 区间可视化
├── 辅助点预测
├── 关键可信度指标
│
└── ★ 新增: AI 一句话摘要（轻量，非完整分析）
    ├── 一行文字："AI 认为：本次预测主要受昨日动量延续和大盘 Beta 驱动"
    └── "查看完整 AI 解读 →"链接（跳转 Intraday 页或展开详情）
```

### 14.5 ★ 新增公共组件

| 组件 | 文件 | 用途 |
|---|---|---|
| `AiAnalysisPanel` | `components/AiAnalysisPanel.vue` | AI 分析完整面板（用于 Intraday） |
| `NewsSourceList` | `components/NewsSourceList.vue` | 新闻来源列表（可复用于多个页面） |

两个组件均接受 `fund_code` 作为 props，内部自行调用对应 API，不依赖父组件传入数据，可独立嵌入任何页面。

---

## 15. 日志系统（不变）

（内容与 v2.5.4 保持一致，略）

---

## 16. 新闻聚合模块 `[NEW]`

### 16.1 模块定位

`news_service.py` 是独立的新闻聚合服务，不依赖 AI 模块。主要职责：

1. 通过 AKShare 从多个源拉取财经新闻；
2. 基于基金画像（持仓股名称、基金类型关键词）计算相关性得分；
3. 过滤、排序、返回最相关的新闻列表。

AI 分析服务（§17）消费此模块的输出。前端也可以直接调用 `/api/v1/fund/{code}/news` 独立展示新闻列表。

### 16.2 AKShare 新闻接口说明

| 接口函数 | 数据源 | 更新频率 | 返回字段 | 适用场景 |
|---|---|---|---|---|
| `ak.stock_telegraph_cls_em()` | 财联社电报 | 实时（分钟级） | `time`、`content` | 盘中实时快讯，速度最快 |
| `ak.stock_news_em(symbol)` | 东方财富个股新闻 | 每小时 | `title`、`content`、`url`、`datetime` | 针对具体股票/基金的深度新闻 |
| `ak.stock_news_sina(symbol)` | 新浪财经 | 实时 | `title`、`datetime`、`url` | 备用源，title-only，内容少 |

**接口调用注意事项**:

- `stock_telegraph_cls_em()` 返回的是全市场电报，不区分标的，需要在结果上做关键词过滤；
- `stock_news_em(symbol=fund_code)` 的 `symbol` 参数支持基金代码，但部分基金代码可能无结果（新基金或数据源未收录），此时应降级为按重仓股代码分别查询后合并；
- 两个接口均不需要 API Key，但高频调用（>10次/分钟）可能触发 IP 限速，应结合 `news_cache_minutes=10` 的缓存策略规避。

### 16.3 相关性计算逻辑

```
输入: 新闻列表 (title + content), 基金画像
  │
  ├─ 1. 构建关键词集合（来自基金画像）
  │       keywords = {
  │         基金名称核心词（去掉"基金""混合""增强"等通用词）,
  │         前5大重仓股名称,
  │         基金类型关键词（equity_active→["A股","沪深","基金经理名"])
  │       }
  │
  ├─ 2. 对每条新闻计算相关性得分
  │       text = title + " " + content[:300]
  │       score = Σ(关键词命中次数 × 权重) / len(keywords)
  │
  │       关键词权重:
  │         重仓股名称命中: +0.4/次
  │         基金名称命中:   +0.3/次
  │         类型关键词命中: +0.1/次
  │       得分区间: [0, 1.0]（超出则截断至1.0）
  │
  ├─ 3. 过滤
  │       去除 score < relevance_min_score 的新闻
  │       去除发布时间超过 36 小时的新闻（盘中估算只看近期）
  │
  ├─ 4. 排序与截断
  │       按 score 降序排列
  │       取前 max_news_for_ai 条送入 AI（默认 3 条）
  │       取前 max_news_for_display 条给前端展示（默认 5 条）
  │
  └─ 输出: NewsResult(items: List[NewsItem], fetched_at: datetime)
```

### 16.4 新闻缓存策略

```
首次调用（或缓存过期）:
  并发执行 Task A + Task B:
    Task A: ak.stock_telegraph_cls_em()    → 财联社电报
    Task B: ak.stock_news_em(fund_code)    → 东方财富个股
  合并结果 → 去重（按 title 哈希） → 计算相关性 → 写缓存

缓存命中（10分钟内）:
  直接返回缓存（不重新调用 AKShare）

缓存设计:
  Key:   f"news:{fund_code}:{date_str}:{hour}:{minute//10}"
  Value: NewsResult JSON
  存储:  SQLite 临时表（非进程内存，重启不丢失）
  TTL:   10 分钟（通过写入时间字段判断，不依赖外部 TTL 机制）
```

### 16.5 降级与异常处理

| 场景 | 行为 |
|---|---|
| AKShare 接口超时（>8s） | 返回空列表，不抛异常，AI 分析继续（但无新闻输入） |
| 财联社接口失败 | 自动降级为仅东方财富 |
| 两个接口均失败 | 返回 `{"items": [], "error": "news_fetch_failed"}`，AI 接收空新闻列表，分析仍然执行（纯基于模型估算数据） |
| 无相关新闻（全部低于阈值） | 返回空列表，AI Prompt 中对应区域填写"今日暂无直接相关新闻" |

---

## 17. AI 分析服务 `[NEW]`

### 17.1 模块定位

`ai_analysis_service.py` 负责：

1. 根据配置路由到对应 AI Provider（GLM 或 SiliconFlow）；
2. 调用 Prompt 模板引擎组装 Prompt（按基金类型选择不同模板）；
3. 发起 HTTP 请求调用外部 AI API；
4. 解析响应，强制提取 JSON 结构化结果；
5. 缓存当日分析结果，避免对同一基金重复计费。

### 17.2 Provider 路由机制

两个 Provider 均遵循 OpenAI 兼容的 Chat Completions 接口格式，可使用统一的 HTTP 客户端层。

```
Provider Router
  │
  ├─ 检查 primary provider 可用性（启动时预热检测）
  │
  ├─ 调用 primary provider（GLM）
  │     URL: https://open.bigmodel.cn/api/paas/v4/chat/completions
  │     Headers:
  │       Authorization: Bearer {GLM_API_KEY}
  │       Content-Type: application/json
  │     Body:
  │       model: "glm-4-flash"
  │       messages: [{role: "user", content: prompt}]
  │       temperature: 0.3
  │       max_tokens: 512
  │
  ├─ 若 primary 失败（超时 / 5xx / 余额不足）:
  │     → 自动切换 fallback provider（SiliconFlow）
  │         URL: https://api.siliconflow.cn/v1/chat/completions
  │         Headers:
  │           Authorization: Bearer {SILICONFLOW_API_KEY}
  │           Content-Type: application/json
  │         Body:
  │           model: "Qwen/Qwen2.5-7B-Instruct"
  │           messages: [{role: "user", content: prompt}]
  │           temperature: 0.3
  │           max_tokens: 512
  │
  └─ 若两者均失败:
       → 抛出 AIProviderError，返回 503，附带仅新闻的降级响应
```

**Provider 选型依据**:

| Provider | 模型 | 特点 | 成本参考 |
|---|---|---|---|
| 智谱 GLM（主） | `glm-4-flash` | 中文理解优秀，金融术语准确，响应快（3-5s） | 约 ¥0.001/千 tokens，极低 |
| 智谱 GLM（备选） | `glm-4-air` | 更强的推理能力，适合复杂分析 | 约 ¥0.004/千 tokens |
| 硅基流动（备） | `Qwen/Qwen2.5-7B-Instruct` | 有免费额度，中文表现好 | 有免费 token 额度，超出后约 ¥0.035/百万 tokens |
| 硅基流动（备选） | `deepseek-ai/DeepSeek-V2.5` | 推理更强，适合复杂分析 | 约 ¥1.33/百万 tokens |

> 每次 AI 分析约消耗 800-1200 tokens（Prompt ~600 + 输出 ~400）。
> 按每日 50 只基金分析估算，GLM-4-Flash 日均成本约 ¥0.06，全年约 ¥22，可忽略不计。

### 17.3 Prompt 模板体系

不同基金类型使用不同的 Prompt 模板，聚焦各自的核心驱动因子。所有模板共享同一个**输出格式约束**（见末尾）。

#### 基础结构（所有模板通用）

```
[角色设定]
你是一位专业的中国基金分析师。请根据以下信息，生成一份简短的当日分析报告。

[基金信息]
代码：{fund_code}
名称：{fund_name}
类型：{fund_type_display}
{type_specific_info}   ← 各模板差异化内容

[估算/预测数据]
今日估算涨跌幅：{estimated_return:%}
置信区间：[{lower_bound:%}, {upper_bound:%}]
估算方法：{method_display}
{holdings_freshness_note}   ← 持仓时效说明

[今日相关新闻]（共{news_count}条，无则填写"暂无直接相关新闻"）
{news_content}

[输出要求]
请严格按照以下JSON格式输出，不要输出任何JSON以外的内容（不要有```json标记）：
{
  "summary": "总体分析（100字以内，客观表述，不做投资承诺）",
  "key_drivers": [
    {"factor": "驱动因素名称", "direction": "正向或负向", "desc": "一句话说明"}
  ],
  "risk_factors": ["风险点1", "风险点2"],
  "suggested_action": "以下四个之一：增持/持有/减持/观望",
  "suggested_action_reason": "建议理由（30字以内）"
}
注意：suggested_action 只能是"增持""持有""减持""观望"之一，不得输出其他词语。
```

#### 偏股/主动股票型（`equity_template.py`）

`type_specific_info` 部分：

```
前十大重仓股（按权重）：
{top10_holdings_list}

重仓股今日估算涨跌（基于实时行情）：
{holdings_realtime_summary}

主要行业暴露：{sector_exposure}
风格偏向：{style_label}（大盘/小盘/成长/价值）

请重点分析：
1. 重仓股今日表现对净值的贡献
2. 大盘指数走势的影响（β效应）
3. 行业或主题的近期催化剂
```

#### 债券型（`bond_template.py`）

`type_specific_info` 部分：

```
估算组合久期：{duration}年
债券类型：{bond_subtype_display}

今日关键利率数据（来自AKShare）：
- 10年期国债收益率变动：{cn10y_change} BP
- 期限利差（10Y-2Y）：{term_spread} BP，较昨日变动 {term_spread_change} BP
- DR007：{dr007}%
- 信用利差（AAA）：{credit_spread_aaa} BP

请重点分析：
1. 利率变动对债券净值的直接影响（公式：ΔNAV≈-久期×Δy）
2. 信用利差变化的影响
3. 资金面松紧程度（DR007水平）
（注意：债券基金不受股市涨跌直接影响，请勿将股市新闻作为主要驱动因素）
```

#### 指数/ETF 型（`index_template.py`）

```
标的指数：{target_index_name}（{target_index_code}）
今日标的指数涨跌幅：{target_index_return:%}
跟踪误差（近20日）：{tracking_error_bp} BP

请重点分析：
1. 标的指数今日表现及主要成分股驱动
2. 注意：指数基金净值约等于标的指数涨跌幅，主要分析指数本身的变动原因
```

#### 平衡/灵活混合型（`mixed_template.py`）

```
估算股票仓位：{estimated_equity_position:%}
估算债券仓位：{estimated_bond_position:%}

当日主要市场数据：
- 沪深300：{hs300_return:%}
- 10年国债收益率变动：{cn10y_change} BP

请综合分析股票和债券双方向的影响，根据估算仓位判断哪个方向的贡献更大。
```

### 17.4 AI 输出解析与容错

AI 模型的输出并不总是完美的 JSON，需要多重容错机制：

```
AI 原始输出
  │
  ├─ Step 1: 尝试直接 json.loads(response)
  │     成功 → 进入字段校验
  │
  ├─ Step 2: 失败 → 正则提取 \{.*?\}（re.DOTALL）
  │     成功 → json.loads(match.group())
  │
  ├─ Step 3: 仍失败 → 返回降级结果
  │     {
  │       "summary": response[:200],    ← 截取前200字作为摘要
  │       "key_drivers": [],
  │       "risk_factors": [],
  │       "suggested_action": "观望",   ← 失败时保守默认
  │       "suggested_action_reason": "AI解析异常，建议人工判断"
  │     }
  │
  └─ 字段校验（JSON解析成功后）:
       ├─ suggested_action 不在白名单 → 替换为"观望"
       ├─ summary 超过 300 字 → 截断至 300 字
       ├─ key_drivers 超过 5 条 → 截断至 5 条
       └─ risk_factors 超过 4 条 → 截断至 4 条
```

### 17.5 AI 分析缓存（SQLite 表定义）

在原有 `db/models.py` 中新增 `ai_analysis_cache` 表：

```sql
CREATE TABLE IF NOT EXISTS ai_analysis_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       TEXT NOT NULL,
    trade_date      TEXT NOT NULL,        -- 格式: YYYY-MM-DD（当日缓存当日有效）
    source          TEXT NOT NULL,        -- "intraday" 或 "predict"
    analysis_json   TEXT NOT NULL,        -- 完整分析结果 JSON
    provider_used   TEXT,                 -- "glm" 或 "siliconflow"
    model_used      TEXT,                 -- 具体模型名称
    news_count      INTEGER DEFAULT 0,    -- 使用的新闻条数
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, trade_date, source) -- 同一基金同一日期只存一条
);
```

**缓存失效规则**: 查询时检查 `trade_date == today`，若不一致则视为过期，重新生成。次日清晨无需主动清除，历史数据自然沉底不影响查询性能（可定期归档 30 天以上的记录）。

### 17.6 持仓数据时效标注（输入到 Prompt）

在组装 Prompt 时，持仓相关的信息必须附带时效说明，防止 AI 生成基于过时持仓的误导性分析：

```python
days_since_report = (today - holdings_quarter_end_date).days

if days_since_report <= 30:
    freshness_note = f"（数据较新：{quarter}季报，距今{days_since_report}天，准确性高）"
elif days_since_report <= 60:
    freshness_note = f"（数据适中：{quarter}季报，距今{days_since_report}天，可能存在调仓）"
else:
    freshness_note = f"（数据较旧：{quarter}季报，距今{days_since_report}天，实际持仓可能有较大变化，分析仅供参考）"
```

同时在 Prompt 的系统角色说明中加入：
> "注意：持仓数据来自季报，存在滞后性。当持仓数据较旧时，请在分析中明确说明不确定性，避免过于确定的表述。"

---

## 附录A: 异常处理全景（更新）

| 异常场景 | 抛出异常 | HTTP状态 | 用户看到的信息 |
|---------|---------|---------|--------------|
| 基金代码不存在 | DataFetchError | 502 | "无法获取基金 XXX 数据" |
| 历史数据不足220行 | InsufficientDataError | 422 | "历史数据不足，需要至少220个交易日" |
| 模型文件不存在 | ModelNotFoundError | 404 | "该基金尚未训练模型" |
| 训练过程中OOM | TrainingError | 500 | "训练失败: 内存不足" |
| 预测值NaN | PredictionError | 500 | "预测计算异常" |
| akshare网络超时 | DataFetchError | 502 | "数据源暂时不可用，已使用缓存" |
| 指数数据缺失 | (不抛异常) | 200 | 该指数列为NaN，其他特征正常计算 |
| 校准集<20条 | (不抛异常) | 200 | 使用fallback固定宽度区间 |
| VIF矩阵奇异 | (不抛异常) | 200 | 停止VIF剔除，保留当前特征集 |
| **★ AI Provider 超时/5xx** | **AIProviderError** | **503** | **"AI分析暂不可用，已返回纯新闻结果"** |
| **★ 两个 Provider 均失败** | **AIProviderError** | **503** | **"所有AI Provider不可用，请稍后重试"** |
| **★ AKShare 新闻接口失败** | **(不抛异常)** | **200** | **新闻列表为空，AI分析继续执行** |
| **★ AI 输出 JSON 解析失败** | **(不抛异常)** | **200** | **返回降级结果，summary字段为原始文本截断** |
| **★ API Key 未配置/无效** | **AIProviderError** | **503** | **"AI分析功能未启用，请联系管理员配置API Key"** |

---

## 附录B: 性能关键路径（更新）

| 操作 | 预期耗时 | 优化措施 |
|------|---------|---------|
| 基金净值加载（缓存命中） | <10ms | 内存缓存 + TTL |
| 指数数据获取（5个并发） | 2-5s | ThreadPoolExecutor(5) |
| 特征构建（~80列） | 50-200ms | pandas向量化运算 |
| 因子预筛选（~80个） | 100-500ms | 只对top20做衰减测试 |
| Walk-Forward CV（12轮） | 5-30s | 取决于数据量和模型复杂度 |
| Stacking集成训练 | 1-5s | 4个基础模型 + Ridge元学习器 |
| 保形预测 | <10ms | 分位数计算O(N) |
| 单次预测推理 | <50ms | 模型已加载到内存 |
| **★ AKShare 新闻获取（2源并发）** | **1-3s** | **asyncio并发 + 10分钟缓存** |
| **★ AI 分析（GLM-4-Flash）** | **3-8s** | **当日缓存，命中时 <10ms** |
| **★ AI 分析（SiliconFlow备用）** | **5-15s** | **同上** |
| **★ Intraday 完整响应（含AI）** | **~4-12s（首次）/ <100ms（缓存命中）** | **AI 异步独立加载，不阻塞主估算结果** |

---

## 附录C: AI Provider 接口规范 `[NEW]`

### C.1 智谱 GLM API

**接口地址**: `https://open.bigmodel.cn/api/paas/v4/chat/completions`

**认证方式**: Bearer Token（`Authorization: Bearer {API_KEY}`）

**推荐模型对比**:

| 模型 | 上下文窗口 | 特点 | 推荐场景 |
|---|---|---|---|
| `glm-4-flash` | 128K | 极速，成本最低，日常分析够用 | **默认首选** |
| `glm-4-air` | 128K | 速度快，能力较强 | 复杂持仓分析 |
| `glm-4` | 128K | 最强，但成本高10倍 | 不推荐用于高频场景 |

**请求结构**:

```json
{
  "model": "glm-4-flash",
  "messages": [
    {
      "role": "user",
      "content": "{assembled_prompt}"
    }
  ],
  "temperature": 0.3,
  "max_tokens": 512,
  "top_p": 0.9
}
```

**响应提取**:

```python
response_text = data["choices"][0]["message"]["content"]
```

**错误码处理**:

| HTTP状态 | GLM错误码 | 含义 | 系统行为 |
|---|---|---|---|
| 401 | - | API Key 无效 | 标记 provider 不可用，切换备用 |
| 429 | - | 请求频率过高 | 等待1s后重试，最多2次 |
| 500 | - | 服务端错误 | 切换备用 Provider |
| 200 | `error` 字段存在 | 业务错误（如余额不足） | 日志记录，切换备用 |

---

### C.2 硅基流动 API

**接口地址**: `https://api.siliconflow.cn/v1/chat/completions`

**认证方式**: Bearer Token（同 OpenAI 格式）

**推荐模型对比**:

| 模型 | 特点 | 免费额度 | 推荐场景 |
|---|---|---|---|
| `Qwen/Qwen2.5-7B-Instruct` | 中文理解好，速度快 | **有免费额度** | **默认备用首选** |
| `Qwen/Qwen2.5-72B-Instruct` | 更强，但较慢 | 无 | 不推荐日常使用 |
| `deepseek-ai/DeepSeek-V2.5` | 推理强，适合复杂分析 | 无 | 可选，成本约¥1.33/M tokens |
| `THUDM/glm-4-9b-chat` | GLM 开源版 | 有免费额度 | 备选 |

**请求结构**（与 OpenAI 格式完全兼容）:

```json
{
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "messages": [
    {
      "role": "user",
      "content": "{assembled_prompt}"
    }
  ],
  "temperature": 0.3,
  "max_tokens": 512,
  "stream": false
}
```

**响应提取**（与 OpenAI 格式完全兼容）:

```python
response_text = data["choices"][0]["message"]["content"]
```

---

### C.3 统一 HTTP 客户端层

两个 Provider 的请求格式完全相同（均为 OpenAI Chat Completions 兼容格式），通过统一的 `LLMClient` 类处理，差异仅在 `base_url` 和 `api_key`：

```
LLMClient
  ├── __init__(base_url, api_key, model, timeout, max_tokens, temperature)
  ├── chat(prompt: str) -> str
  │     POST {base_url}/chat/completions
  │     重试逻辑: 失败时最多重试 retry_times 次
  │     超时处理: httpx.AsyncClient timeout=timeout_seconds
  │     响应解析: data["choices"][0]["message"]["content"]
  │
  └── health_check() -> bool
        发送 "ping" prompt，检测 Provider 响应是否正常
        用于启动时预热检测和 /api/v1/ai/provider-status 接口
```

---

*文档结束 | 版本 v2.6.0 | 基于 v2.5.4 增量更新*
