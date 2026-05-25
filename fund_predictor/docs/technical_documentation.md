# 基金 T+1 净值涨跌幅区间预测系统 — 技术文档

> 版本: v2.5.4 | 更新: 2026-05-24
> 本文档完整描述系统的架构、数据流、计算逻辑、判断分支和配置参数。

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [目录结构与模块依赖](#2-目录结构与模块依赖)
3. [端到端数据流](#3-端到端数据流)
4. [基金分类路由系统](#4-基金分类路由系统)
5. [数据获取层](#5-数据获取层)
6. [特征工程](#6-特征工程)
7. [因子预筛选](#7-因子预筛选)
8. [模型训练与选择](#8-模型训练与选择)
9. [集成学习（Stacking）](#9-集成学习stacking)
10. [后处理：保形预测与净值约束](#10-后处理保形预测与净值约束)
11. [冷启动机制](#11-冷启动机制)
12. [API 接口规范](#12-api-接口规范)
13. [配置参数手册](#13-配置参数手册)
14. [前端架构](#14-前端架构)
15. [日志系统](#15-日志系统)

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
  ├─> cold_start.py                 (历史<120天时启用)
  └─> intraday_service.py           (T日日内估计)
```

---

## 3. 端到端数据流

以 **用户发起一次基金预测** 为例，完整的数据流如下：

```
用户点击"预测"按钮 (前端 Predict.vue)
  │
  ├─① POST /api/v1/fund/predict { fund_code: "110011" }
  │
  ▼
[FastAPI 中间件] request_context()
  ├─ 生成 request_id (uuid hex[:12])
  ├─ 设置 ContextVar: request_id, fund_code="-", stage="request_in"
  ├─ 记录日志: app.log + api.jsonl
  └─ 启动计时 (time.perf_counter)
  │
  ▼
[fund.py] predict_fund()
  │
  ├─② fund_profile_service.classify_fund("110011")
  │     判断路径:
  │     ├─ 有 benchmark? → 按 benchmark 映射类型
  │     ├─ 无 benchmark 但有 name 关键词? → 按名称推断
  │     └─ 都没有? → 默认 hybrid_equity
  │     返回: FundProfile(fund_type, fund_name, skip_prediction, ...)
  │
  ├─③ routing_service.route_predict(profile)
  │     判断路径:
  │     ├─ skip_prediction=True? → 返回"货币基金无需预测"
  │     ├─ fund_type in ("hybrid_equity", "equity_active")?
  │     │   └─→ prediction_service.predict_next()  ← 主流程
  │     ├─ fund_type == "money_market"? → 返回"净值恒为1"
  │     └─ 其他? → prediction_service.predict_next() (通用流程)
  │
  ▼
[prediction_service.py] predict_next(fund_code="110011")
  │
  ════════════════════════════════════════════════
  Step 1: 数据获取 (data_service.fetch_training_data)
  ════════════════════════════════════════════════
  │
  ├─ 读取本地CSV: data/raw/fund_nav/110011.csv
  │     缓存策略:
  │     ├─ 内存缓存 (_NAV_CACHE dict) → TTL=cache_stale_days(10天)
  │     └─ 文件mtime检查 → 若未过期直接返回缓存DataFrame
  │
  ├─ 并发获取指数数据 (ThreadPoolExecutor(max_workers=5)):
  │     ├─ hs300 (沪深300)  → akshare 或 本地CSV fallback
  │     ├─ zz500 (中证500)  → 同上
  │     ├─ zz1000 (中证1000) → 同上
  │     ├─ cyb (创业板指)    → 同上
  │     ├─ kcb50 (科创50)    → 同上
  │     ├─ sh000688 (上证红利)
  │     └─ sz399006 (创业板R)
  │     fallback链: akshare API → 本地data/raw/index/*.csv → NaN填充
  │
  ├─ 获取持仓数据: holdings_service.get_latest_holdings()
  │     来源: data/raw/holdings/110011.csv
  │
  ├─ 合并: fund_nav LEFT JOIN index_data ON date
  │     新增列: hs300_ret, zz500_ret, ..., cyb_ret, kcb50_ret 等
  │
  └─ 返回: DataFrame(columns=[date, nav, daily_growth_pct, ...])
  │
  ════════════════════════════════════════════════
  Step 2: 特征构建 (feature_service.build_features)
  ════════════════════════════════════════════════
  │
  ├─ 2a. Lag 特征 (lookback_lags = [1,2,3,5,10])
  │     for lag in [1,2,3,5,10]:
  │       df[f"fund_ret_lag{lag}"] = df["daily_growth_pct"].shift(lag)
  │
  ├─ 2b. Rolling 统计 (rolling_windows = [5,10,20,60])
  │     for w in [5,10,20,60]:
  │       df[f"fund_ret_mean_{w}"]  = df["daily_growth_pct"].rolling(w).mean()
  │       df[f"fund_ret_std_{w}"]   = df["daily_growth_pct"].rolling(w).std()
  │       df[f"fund_ret_max_{w}"]   = df["daily_growth_pct"].rolling(w).max()
  │       df[f"fund_ret_min_{w}"]   = df["daily_growth_pct"].rolling(w).min()
  │       df[f"fund_ret_skew_{w}"]  = df["daily_growth_pct"].rolling(w).skew()
  │       df[f"fund_ret_kurt_{w}"]  = df["daily_growth_pct"].rolling(w).kurt()
  │
  ├─ 2c. Beta 特征 (beta_window = 20)
  │     对每个指数 idx ∈ {hs300, zz500, zz1000, cyb, kcb50}:
  │       if f"{idx}_ret" in df.columns:
  │         beta = cov(fund_ret, idx_ret) / var(idx_ret)  (20日滚动窗口)
  │         df[f"beta_{idx}"] = rolling_beta
  │
  ├─ 2d. 回撤特征
  │     df["drawdown_20d"] = (nav - rolling_max(nav, 20)) / rolling_max(nav, 20)
  │     df["drawdown_60d"] = (nav - rolling_max(nav, 60)) / rolling_max(nav, 60)
  │     df["max_drawdown_20d"] = rolling_max(drawdown_20d)
  │
  ├─ 2e. 动量特征
  │     df["mom_5d"]  = nav / nav.shift(5)  - 1
  │     df["mom_20d"] = nav / nav.shift(20) - 1
  │     df["mom_60d"] = nav / nav.shift(60) - 1
  │
  ├─ 2f. 波动率比
  │     for w in [20, 60]:
  │       vol_fund = std(daily_growth_pct, w)
  │       if "hs300_ret" in df.columns:
  │         vol_idx  = std(hs300_ret, w)
  │         df[f"vol_ratio_{w}d"] = vol_fund / (vol_idx + 1e-8)
  │
  ├─ 2g. 风格暴露 (style_window = 60)
  │     条件判断: 仅当对应指数收益率列存在时计算
  │     IF "cyb_ret" AND "hs300_ret" 存在:
  │       style_growth_vs_large = cyb_ret - hs300_ret  (成长 vs 大盘)
  │     IF "zz1000_ret" AND "hs300_ret" 存在:
  │       style_small_vs_large = zz1000_ret - hs300_ret  (小盘 vs 大盘)
  │     IF "kcb50_ret" AND "hs300_ret" 存在:
  │       style_tech_vs_large = kcb50_ret - hs300_ret  (科技 vs 大盘)
  │     对每个风格列: 计算 mean_5 和 mean_20 的滚动均值
  │
  ├─ 2h. 增强特征 (按需加载)
  │     ├─ enhanced_equity_features.build():
  │     │   ├─ 市场情绪: 涨跌家数比、新高新低比、成交额变化率
  │     │   ├─ 日历效应: 月初/月末/周一/周五哑变量
  │     │   └─ 动量质量: 上行/下行波动比、偏度
  │     ├─ bond_features.build(): (债券类基金专用)
  │     │   ├─ 物理先验: -duration × Δy (利率变动对净值的直接影响)
  │     │   ├─ 利率曲线: 期限结构斜率、信用利差
  │     │   └─ 流动性指标
  │     └─ macro_features.build():
  │         ├─ 债券收益率(CPI/PPI相关)
  │         ├─ PMI/工业增加值
  │         └─ 北向资金流向
  │
  ├─ 2i. 目标变量
  │     df["target_next"] = df["daily_growth_pct"].shift(-1)  # T+1 收益率
  │
  └─ 返回: DataFrame(~80+列特征)
  │
  ════════════════════════════════════════════════
  Step 3: 因子预筛选 (factor_screening.pre_screen_factors)
  ════════════════════════════════════════════════
  │
  输入: ~80个候选特征, 目标=target_next
  │
  ├─ 前置条件: 有效样本 < 50? → 跳过筛选，保留全部特征
  │
  ├─ Round 1: IC 检验 (Pearson相关系数)
  │     对每个特征 x:
  │       ic = pearsonr(x, target_next)
  │       IF |ic| < 0.02 AND x 不在白名单:
  │         → 标记为 low_ic, 排除
  │     白名单: ["fund_ret_lag1", "fund_ret_lag2", "hs300_ret", "zz500_ret"]
  │
  ├─ Round 2: VIF 共线性检验 (逐步回归式)
  │     WHILE 存在 VIF > 10.0 的特征:
  │       找出 VIF 最高的特征 → 移除
  │       重新计算剩余特征的 VIF
  │     直到所有 VIF ≤ 10.0 或只剩 < n+10 个样本
  │
  ├─ Round 3: ICIR 稳定性检验
  │     对每个剩余特征:
  │       滚动窗口(60日)计算 IC 序列
  │       ICIR = mean(IC) / std(IC)
  │       IF ICIR < 0.5 → 标记为 low_icir, 排除
  │
  ├─ Round 4: 衰减测试 (仅 top20 特征)
  │     计算 lag=[1,3,5,10,15,20] 的延迟IC
  │     decay_rate = (IC_lag1 - IC_lag10) / IC_lag1
  │     记录最佳滞后期和衰减速度
  │
  └─ 输出: FactorScreeningResult
        ├─ screened_features: 最终保留的特征列表 (~30-50个)
        ├─ removed_features: 被移除的特征及原因
        └─ screening_summary: 各轮移除数量统计
  │
  ════════════════════════════════════════════════
  Step 4: 模型训练与选择 (model_selection_service)
  ════════════════════════════════════════════════
  │
  ├─ 4a. 四段数据划分
  │     总数据 N 行, 按时间顺序切分:
  │     ┌─────────┬─────────┬──────────┬─────────┐
  │     │ Train   │ Valid   │ Test_sel │ Test_fin │
  │     │ 55%     │ 22%     │ 13%      │ 10%     │
  │     │ ~N×0.55 │ ~N×0.22 │ ~N×0.13  │ ~N×0.10 │
  │     └─────────┴─────────┴──────────┴─────────┘
  │
  │     判断: len(df) < MIN_TRAIN_ROWS(220)?
  │       YES → raise InsufficientDataError
  │
  ├─ 4b. 候选模型列表
  │     models_to_try = [
  │       ("ridge",       Ridge(alpha=1.0)),
  │       ("elasticnet",  ElasticNet(alpha=0.01)),
  │       ("lgbm",        LGBMRegressor(n_estimators=120, max_depth=5,
  │                                     learning_rate=0.05, min_samples_leaf=10)),
  │       ("xgboost",     XGBRegressor(n_estimators=120, max_depth=5,
  │                                     learning_rate=0.05)),
  │     ]
  │     注意: LightGBM 可能不可用 (lightgbm_not_available warning)
  │
  ├─ 4c. Walk-Forward 交叉验证 (ensemble.walk_forward_cv)
  │     参数:
  │       train_months = 24   (约500交易日)
  │       valid_months = 3    (约60交易日)
  │       step_months  = 1    (每月滚动)
  │       min_rounds    = 12   (最少验证12轮)
  │
  │     每轮执行:
  │     for offset in range(start, N-valid_size, step_size):
  │       X_train = df[offset-train_size : offset]
  │       X_valid = df[offset : offset+valid_size]
  │
  │       样本权重: w[i] = exp(-ln(2) * i / halflife(60))
  │                 (越近的样本权重越高, 半衰期60天)
  │
  │       model.fit(X_train, y_train, sample_weight=w)
  │       pred = model.predict(X_valid)
  │
  │       记录: MAE, RMSE, Corr
  │
  │     聚合: mean_mae, median_mae, worst_mae, best_mae, mean_corr
  │
  ├─ 4d. 模型选择决策
  │     选择标准: valid_mae 最小
  │     best_model = min(models, key=lambda m: m.valid_mae)
  │
  ├─ 4e. 方向校准 (isotonic回归)
  │     将连续预测值映射到方向概率
  │     方法: IsotonicRegression(二分类标签: up/down)
  │
  ├─ 4f. Stacking 集成 (ensemble.StackingEnsemble)
  │     Layer 1: 各基础模型的 out-of-fold 预测作为元特征
  │     Layer 2: Ridge(alpha=1.0) 元学习器线性组合
  │     权重: coef_ 反映各模型在不同市场环境下的贡献度
  │
  └─ 输出: 最佳模型 + metrics.json + model.pkl
  │
  ════════════════════════════════════════════════
  Step 5: 保形预测置信区间 (conformal.conformal_interval)
  ════════════════════════════════════════════════
  │
  输入: 已训练model, 校准集(X_calib, y_calib), 新样本X_new, alpha=0.10
  │
  ├─ 前置判断: len(X_calib) < 20?
  │     YES → fallback: ±2 × |pred| × 0.02 (固定宽度区间)
  │
  ├─ 计算非一致性得分:
  │     calib_pred = model.predict(X_calib)
  │     scores = |y_calib - calib_pred|  (每个校准样本的绝对误差)
  │
  ├─ 计算阈值:
  │     threshold = quantile(scores, 1-alpha)  (= 90th percentile)
  │     含义: 90%的历史误差不超过此阈值
  │
  ├─ 构建预测区间:
  │     new_pred = model.predict(X_new)
  │     lower = new_pred - threshold
  │     upper = new_pred + threshold
  │
  └─ 自适应变体 (adaptive_conformal_interval):
        IF volatility_col 存在:
          adjustment = clip(vol / median_vol, 0.7, 2.0)
          half_width *= adjustment  (高波动时扩大, 低波动时收窄)
  │
  ════════════════════════════════════════════════
  Step 6: 净值约束 (constraints.apply_nav_constraints)
  ════════════════════════════════════════════════
  │
  按 fund_type 查表 NAV_LIMITS:
  │
  │  fund_type              │ limit (日收益率上限)
  │  ───────────────────────┼────────────────────
  │  hybrid_equity          │ ±20%
  │  equity_active          │ ±20%
  │  hybrid_balanced        │ ±15%
  │  hybrid_bond            │ ±10%
  │  hybrid_flexible        │ ±20%
  │  bond_pure              │ ±5%
  │  bond_mixed             │ ±8%
  │  bond_convertible       │ ±20%
  │  index_equity           │ None (不约束,跟随标的)
  │  index_bond             │ None
  │  fof                    │ ±15%
  │  qdii                   │ ±20%
  │
  │  判断逻辑:
  │  IF pred_return < -limit → clipped = -limit, is_clipped=True
  │  ELIF pred_return > limit → clipped = +limit, is_clipped=True
  │  ELSE → clipped = pred_return, is_clipped=False
  │
  │  裁剪后置信度降级: is_clipped=True → confidence_adjustment = "low"
  │
  ├─ 特殊时期置信度调整 (adjust_confidence_for_special_periods):
  │     检查项 (可叠加):
  │     ├─ 季报窗口 (3/6/9/12月 18-31日): penalty -15%
  │     ├─ 月末效应 (≥28日): penalty -5%
  │     ├─ 年末效应 (12月 ≥20日): penalty -10%
  │     └─ 经理变更 (<90天): penalty -25%
  │     总惩罚上限: -40%
  │
  └─ 返回最终结果给前端
  │
  ▼
[FastAPI 中间件] response 处理
  ├─ elapsed_ms = time.perf_counter() - start_time
  ├─ 响应头: X-Request-ID, X-Response-Time-ms
  ├─ 记录 api.jsonl (method/path/status/elapsed_ms)
  └─ stage = "request_done"
  │
  ▼
[前端] 显示预测结果
  ├─ 预测值 (如: +0.35%)
  ├─ 置信区间 (如: [-0.82%, +1.52%])
  ├─ 方向概率 (如: 看多 62%)
  ├─ 基金画像 (type/name/size/benchmark)
  └─ 模型信息 (MAE/使用的特征数/训练日期)
```

---

## 4. 基金分类路由系统

### 4.1 三级分类逻辑 (`fund_profile_service.py`)

```python
def classify_fund(fund_code: str) -> FundProfile:
```

**Level 1 — Benchmark 映射** (最优先):

| benchmark 关键字 | fund_type |
|---|---|
| 沪深300 / 中证100 / 中证800 | `equity_active` |
| 中证500 / 中证1000 | `equity_active` |
| 创业板指 / 科创50 | `equity_active` |
| 中证全债 / 中证综合债 | `bond_pure` |
| 中证转债 | `bond_convertible` |
| 沪深300 * 中证全债 | `hybrid_balanced` |
| 沪深300 * 50% + 中证全债 * 50% | `hybrid_balanced` |
| 无基准但有"货币"/"现金"关键词 | `money_market` (skip_prediction=True) |

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

### 4.2 路由决策树 (`routing_service.py`)

```
输入: FundProfile
  │
  ├─ skip_prediction == True?
  │   └─→ 返回 "货币基金无需预测"
  │
  ├─ fund_type in ("hybrid_equity", "equity_active")?
  │   └─→ predict_next()  (成熟ML流水线)
  │
  ├─ fund_type == "money_market"?
  │   └─→ 返回 "净值恒为1"
  │
  ├─ fund_type == "index_equity"?
  │   └─→ predict_next() + TODO: 规则引擎替换
  │
  └─ 其他 (bond/fof/qdii/hybrid_*)?
      └─→ predict_next()  (通用ML流程)
```

---

## 5. 数据获取层

### 5.1 缓存策略 (`data_service.py`)

```python
_NAV_CACHE: dict[str, tuple[DataFrame, datetime]] = {}
```

**缓存命中判断**:

```python
def _is_stale(cached_at: datetime) -> bool:
    return (datetime.now() - cached_at).days >= cache_stale_days  # 默认10天
```

**获取流程**:

```python
def fetch_fund_nav(fund_code: str, require_fresh: bool = False) -> DataFrame:
    # 1. 检查内存缓存
    cached = _NAV_CACHE.get(fund_code)
    if cached and not require_fresh and not _is_stale(cached[1]):
        return cached[0]

    # 2. 从本地CSV加载
    df = pd.read_csv(RAW_DIR / "fund_nav" / f"{fund_code}.csv")

    # 3. 更新缓存
    _NAV_CACHE[fund_code] = (df, datetime.now())
    return df
```

### 5.2 并发指数获取

```python
with ThreadPoolExecutor(max_workers=fetch_max_workers) as pool:
    futures = {
        pool.submit(fetch_index_data, idx): idx
        for idx in INDEX_CODES
    }
    for future in as_completed(futures):
        idx = futures[future]
        try:
            index_dfs[idx] = future.result(timeout=fetch_timeout_seconds)
        except Exception:
            logger.warning("index_fetch_failed index=%s", idx)
```

**Fallback 链**:

```
akshare.index_zh_a_hist() API
  ↓ 失败 (ProxyError/Timeout/503)
data/raw/index/{idx}.csv 本地文件
  ↓ 失败 (文件不存在)
NaN 填充 (该指数列全为空)
```

### 5.3 数据合并

```python
df = fund_nav_df.merge(hs300_df[["date", "hs300_ret"]], on="date", how="left")
for idx in other_indices:
    df = df.merge(idx_df, on="date", how="left")  # LEFT JOIN 保证基金数据不丢失
```

---

## 6. 特征工程

### 6.1 核心特征公式汇总

| 特征类别 | 公式 | 参数 | 输出列数 |
|---------|------|------|---------|
| **Lag** | `ret[t-lag]` | lag∈{1,2,3,5,10} | 5 |
| **Rolling Mean** | `mean(ret[t-w:t])` | w∈{5,10,20,60} | 4 |
| **Rolling Std** | `std(ret[t-w:t])` | w∈{5,10,20,60} | 4 |
| **Rolling Min/Max** | `min(ret[t-w:t])`, `max(...)` | w∈{5,10,20,60} | 8 |
| **Rolling Skew/Kurt** | `skew(...)`, `kurt(...)` | w∈{5,10,20,60} | 8 |
| **Beta** | `cov(ret_fund, ret_idx) / var(ret_idx)` | window=20, idx∈5个 | ≤5 |
| **Drawdown** | `(nav - rolling_max(nav)) / rolling_max(nav)` | w∈{20,60} | 4 |
| **Momentum** | `nav[t]/nav[t-n] - 1` | n∈{5,20,60} | 3 |
| **Vol Ratio** | `std(ret_fund) / std(ret_hs300)` | w∈{20,60} | ≤2 |
| **Style** | `ret_cyb - ret_hs300` 等 | 条件存在 | ≤6 |
| **Enhanced Equity** | 涨跌比/日历/动量质量 | — | ~15 |
| **Bond Physics** | `-duration × Δy` | duration∈{1.5~3.0} | ~8 |
| **Macro** | CPI/PMI/北向资金 | — | ~5 |
| **Target** | `ret[t+1]` | shift(-1) | 1 |

**总计**: 约 70-85 个原始特征 → 筛选后 30-50 个

### 6.2 债券物理先验 (`bond_features.py`)

核心公式 — 利率变动对债券净值的直接影响:

```
ΔNAV ≈ -duration × Δy - OAS_spread_change + daily_fee

其中:
  duration: 根据基金类型估算 (纯债3.0年, 混合债2.5年, 可转债1.5年)
  Δy: 国债到期收益率变动
  OAS: 期权调整利差
  daily_fee: 日均管理费 (默认 0.0003%)
```

### 6.3 样本时间权重 (`ensemble.build_sample_weights`)

```python
weights[i] = exp(-ln(2) * i / halflife)   # halflife = 60
```

含义: 最新样本权重 = 1.0, 60天前样本权重 = 0.5, 120天前 = 0.25

---

## 7. 因子预筛选

### 7.1 四轮筛选流程

```
输入: ~80 个候选特征
  │
  ▼
Round 1: IC 过滤 (阈值: |IC| ≥ 0.02)
  保留: 与目标相关性显著的特征
  白名单豁免: fund_ret_lag1, fund_ret_lag2, hs300_ret, zz500_ret
  ↓ (~移除 10-20 个弱相关特征)
  ▼
Round 2: VIF 共线性消除 (阈值: VIF ≤ 10)
  方法: 逐步回归 (每次剔除VIF最高者, 重算)
  ↓ (~移除 5-15 个冗余特征)
  ▼
Round 3: ICIR 稳定性过滤 (阈值: ICIR ≥ 0.5)
  ICIR = mean(rolling_IC) / std(rolling_IC)
  含义: 因子的预测能力是否稳定 (高IC但波动大也不可靠)
  ↓ (~移除 5-10 个不稳定特征)
  ▼
Round 4: 衰减测试 (仅top20)
  验证因子的信息是否随时间快速衰减
  输出: 最佳滞后期, 衰减速率
  ↓ (仅记录, 不做硬性排除)
  ▼
输出: screened_features (~30-50 个)
```

### 7.2 关键判断条件

| 条件 | 动作 |
|------|------|
| 有效样本 < 50 | 跳过全部筛选, 保留所有特征 |
| 特征非数值/含NaN过多 | IC记为None, 跳过该特征 |
| VIF计算矩阵奇异 (n < p+10) | 停止VIF循环 |
| ICIR滚动窗口不足5段 | ICIR记为None, 跳过ICIR判断 |

---

## 8. 模型训练与选择

### 8.1 四段数据划分

```
时间轴 ─────────────────────────────────────────────►
       |--------Train 55%-------|--Valid 22%--|-Test13%|-Fin10%|
       0                      T*0.55         T*0.77  T*0.90  T*1.0
```

**用途说明**:
- **Train (55%)**: 模型参数拟合
- **Valid (22%)**: 模型选择 (选MAE最小的)、Stacking元学习器训练
- **Test_select (13%)**: 最终模型确认 (一次性使用, 不参与调参)
- **Test_final (10%)**: 泛化性能报告 (仅在报告中展示)

### 8.2 Walk-Forward CV 示意图

```
Round 1:  [====Train====][==Valid==]                  .
Round 2:  .[====Train====][==Valid==]                 .
Round 3:  ..[====Train====][==Valid==]                .
...                                              .
Round N:  ..............[====Train====][==Valid==]

每轮: Train固定24个月, Valid固定3个月, 向前滚动1个月
最少12轮, 最多24轮 (min_rounds=12, 额外12轮缓冲)
```

### 8.3 模型选择决策

```python
best_model_name = min(cv_results, key=lambda r: r["valid_mae"])
best_model = trained_models[best_model_name]
```

**选择依据**: 验证集平均绝对误差 (MAE) 最小
**备选**: 若MAE相近(<10%差异), 优先选择更简单的模型 (Ridge > ElasticNet > LGBM > XGBoost)

---

## 9. 集成学习（Stacking）

### 9.1 两层架构

```
Layer 1: Base Models (并行)
┌─────────────┬──────────────┬─────────────┬──────────────┐
│   Ridge     │  ElasticNet  │    LGBM     │   XGBoost    │
│ pred_ridge  │ pred_enet    │ pred_lgbm   │ pred_xgb     │
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
│  权重约束: L2正则化 (alpha=1.0)                   │
└──────────────────────────────────────────────────┘
```

### 9.2 元学习器训练条件

```python
if len(X_meta) < 20 or np.any(np.isnan(X_meta)):
    # 验证集太小或含NaN → 跳过Stacking, 使用单模型
    self.fitted = False
    return {"status": "skipped"}
```

### 9.3 残差自适应修正 (Layer 3)

```python
bias = mean(recent_errors[-10:])  # 最近10次预测的平均偏差
corrected_pred = current_pred - bias
```

---

## 10. 后处理：保形预测与净值约束

### 10.1 保形预测算法

```
输入: model, 校准集(X_calib, y_calib), 显著水平 α=0.10

步骤:
1. 在校准集上预测: ŷ_calib = model.predict(X_calib)
2. 计算得分: s_i = |y_i - ŷ_i|  (每个样本的绝对残差)
3. 取分位数: Q = quantile(s, 1-α)  (= 第90百分位)
4. 新样本预测: ŷ_new = model.predict(X_new)
5. 区间: [ŷ_new - Q, ŷ_new + Q]

统计保证: P(y_new ∈ [ŷ_new-Q, ŷ_new+Q]) ≥ 1-α = 90%

Fallback (校准集 < 20条):
  interval = ŷ_new ± 2 × |ŷ_new| × 0.02  (固定±2%)
```

### 10.2 自适应调整

```python
if 当前波动率 > 中位数波动率:
    区间宽度 × max(1.0, vol/median_vol)  (最大2倍放大)
else:
    区间宽度 × max(0.7, vol/median_vol)  (最小0.7倍收缩)
```

### 10.3 净值约束规则

```
输入: pred_return (预测日收益率), fund_type

查表 NAV_LIMITS[fund_type] → limit

IF limit is None:
    → 不裁剪 (指数型基金跟随标的)

ELIF pred_return < -limit:
    → clipped = -limit, confidence = "low"

ELIF pred_return > limit:
    → clipped = +limit, confidence = "low"

ELSE:
    → clipped = pred_return, confidence = "normal"
```

### 10.4 特殊时期置信度调整

| 触发条件 | 时间范围 | 罚分 | 可叠加 |
|---------|---------|------|-------|
| 季报披露窗口 | 3/6/9/12月 18-31日 | -15% | ✅ |
| 月末效应 | 每月≥28日 | -5% | ✅ |
| 年末结算 | 12月≥20日 | -10% | ✅ |
| 经理变更 | 变更后<90天 | -25% | ✅ |

**总罚分上限**: -40%（即最低置信度 = 原始 - 40%）

---

## 11. 冷启动机制

### 11.1 触发条件

```python
should_use_group_model(fund_code):
  history_days = count_rows(fund_nav_csv)
  has_model = exists(model.pkl)

  IF history_days < 120 OR NOT has_model:
    RETURN (True, history_days)  # 使用群体模型
  ELSE:
    RETURN (False, history_days) # 使用个体模型
```

### 11.2 群体模型算法

```
输入: fund_code, fund_type, features(当前特征向量)
  │
  ├─ 1. 找同类型同伴
  │     遍历 models/ 目录下所有已训练模型
  │     WHERE peer.fund_type == fund_type AND peer != self
  │     要求: model.pkl + metrics.json 同时存在
  │
  ├─ 2. 同伴推理
  │     FOR each peer_model:
  │       load(peer/model.pkl)
  │       load(peer/selected_features.json)
  │       pred = model.predict(features[selected_features])
  │
  ├─ 3. 基线聚合
  │     group_baseline = mean(all_peer_predictions)
  │     IF peers < 3: RETURN None (样本不足)
  │
  ├─ 4. 微调修正
  │     recent_mean_ret = mean(fund最近30天的日收益)
  │     blend_weight = history_days / 120  (0~1线性增长)
  │     adjustment = recent_mean_ret × (1-blend_weight) × 0.5
  │
  └─ 5. 最终融合
        final = baseline × (1 - blend_weight×0.5) + adjustment
        blend_weight=0 (0天): 100%群体模型
        blend_weight=0.5 (60天): 75%群体 + 25%微调
        blend_weight=1.0 (120天): 87.5%群体 + 12.5%微调
        blend_weight≥1.0: 过渡到个体模型, RETURN 0.0
```

---

## 12. API 接口规范

### 12.1 接口清单

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

### 12.2 预测接口详情

**请求**: `POST /api/v1/fund/predict`

```json
{
  "fund_code": "110011",
  "prediction_mode": "t_plus_1_close"
}
```

**成功响应** (200):

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
      "features_used": 38,
      "trained_at": "2026-05-23"
    },
    "conformal_meta": {
      "method": "conformal_quantile",
      "interval_width_bp": 234.0,
      "threshold_bp": 117.0
    },
    "constraint_info": {
      "original_return": 0.0035,
      "constrained_return": 0.0035,
      "lower_limit": -0.20,
      "upper_limit": 0.20,
      "is_clipped": false
    },
    "special_period_adjustments": [],
    "fund_profile": {
      "type": "equity_active",
      "name": "易方达中小盘混合",
      "size": "large",
      "manager": "张坤",
      "benchmark": "沪深300指数收益率×80%+中债综合财富指数收益率×20%"
    },
    "prediction_mode": "t_plus_1_close",
    "asof_date": "2026-05-23"
  }
}
```

**错误响应** (统一格式):

```json
{
  "ok": false,
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "基金 110011 历史数据不足220行，当前仅150行",
    "status": 422
  }
}
```

### 12.3 HTTP 状态码映射

| 错误类型 | HTTP Status | code 字段 |
|---------|------------|-----------|
| AppError (基类) | 400 | APP_ERROR |
| DataFetchError | 502 | DATA_FETCH_ERROR |
| ModelNotFoundError | 404 | MODEL_NOT_FOUND |
| InsufficientDataError | 422 | INSUFFICIENT_DATA |
| PredictionError | 500 | PREDICTION_ERROR |
| TrainingError | 500 | TRAINING_ERROR |

---

## 13. 配置参数手册

### 13.1 config.yaml 完整参数说明

```yaml
# === 数据获取 ===
data:
  cache_stale_days: 10        # 缓存过期天数 (内存中的DataFrame)
  min_train_rows: 220         # 最小训练样本数 (低于此抛异常)
  fetch_timeout_seconds: 20   # 单次akshare请求超时
  fetch_max_workers: 5        # 并发获取指数数据的线程数
  fund_nav_fallback_enabled: true   # 基金净值fallback开关
  index_fallback_enabled: true     # 指数数据fallback开关

# === 特征工程 ===
feature:
  lookback_lags: [1, 2, 3, 5, 10]   # Lag特征滞后阶数
  rolling_windows: [5, 10, 20, 60]   # Rolling统计窗口
  beta_window: 20                     # Beta计算窗口
  volatility_window: 20               # 波动率计算窗口
  style_window: 60                    # 风格暴露计算窗口

# === 因子预筛选 ===
screening:
  ic_threshold: 0.02      # IC绝对值下限 (低于此视为无效因子)
  vif_threshold: 10.0     # VIF上限 (高于此视为共线性)
  icir_threshold: 0.5     # ICIR稳定性下限
  decay_window: 20        # 衰减测试窗口

# === 模型训练 ===
model:
  train_split_ratio: [0.55, 0.22, 0.13, 0.10]  # 四段划分比例
  sample_weight_halflife: 60    # 样本权重半衰期 (交易日)
  walk_forward_train_months: 24   # WF-CV训练窗口(月)
  walk_forward_valid_months: 3    # WF-CV验证窗口(月)
  walk_forward_step_months: 1     # WF-CV滚动步长(月)
  walk_forward_min_rounds: 12     # WF-CV最小轮次

  ridge_alpha: 1.0            # Ridge正则化强度
  elasticnet_alpha: 0.01      # ElasticNet正则化
  n_estimators: 120           # 树模型棵数
  max_depth: 5               # 树最大深度
  learning_rate: 0.05         # 学习率
  min_samples_leaf: 10        # 叶节点最小样本

  direction_calibration_method: "isotonic"  # 方向校准方法
  stacking_alpha: 1.0         # Stacking元学习器正则化

# === 区间预测 ===
interval:
  default_alpha: 0.10         # 保形预测显著水平 (→ 90%覆盖率)
  regime_groups: [...]        # 波动率分组
  quantiles: [0.70, 0.80, 0.90, 0.99]  # 分位数

# === 债券因子 ===
bond:
  duration_estimate:
    bond_pure: 3.0           # 纯债久期估算(年)
    bond_mixed: 2.5          # 混合债久期
    bond_convertible: 1.5     # 可转债久期
  daily_fee: 0.000003        # 日均费用 (0.0003%)

# === 净值约束 ===
nav_constraints:             # 各类型日收益率限制
  hybrid_equity: 0.20        # ±20%
  equity_active: 0.20
  bond_pure: 0.05            # ±5%
  ...

# === 冷启动 ===
cold_start:
  group_model_days: 90       # 群体模型主导期(天)
  fine_tune_days: 180        # 微调过渡期(天)
  individual_model_days: 180 # 完全过渡到个体模型(天)

# === 监控与退化 ===
monitoring:
  mae_alert_sigma: 2.0              # MAE异常阈值 (σ倍)
  direction_accuracy_threshold: 0.50 # 方向准确率警戒线
  consecutive_bad_days: 5            # 连续差预测天数
  bias_detection_window: 10          # 偏差检测窗口

# === API ===
api:
  version: "v1"
  request_timeout: 30         # 请求超时(秒)
  max_concurrent_tasks: 3     # 最大并发训练任务

# === 日志系统 ===
logging:
  level: "INFO"
  dir: "logs"
  console: { enabled: true, level: "INFO" }
  file: { encoding: "utf-8", max_bytes: 10485760, backup_count: 30 }
  handlers: { app/api/train/error/audit/perf 各自配置 }
  third_party: { uvicorn/sqlalchemy/akshare/requests: WARNING }
  sampling: { rate: 0.1 }     # 高频接口采样率
```

### 13.2 关键路径常量 (`core/config.py`)

| 常量 | 值 | 说明 |
|------|---|------|
| ROOT_DIR | 项目根目录 | 所有相对路径的基础 |
| RAW_DIR | `{ROOT}/data/raw` | 原始CSV存放 |
| PROCESSED_DIR | `{ROOT}/data/processed` | 处理后数据集 |
| MODEL_DIR | `{ROOT}/models` | 训练模型产出 |
| LOG_DIR | `{ROOT}/logs` | 日志输出 |
| STATIC_DIR | `{ROOT}/static` | 静态资源 |
| MIN_TRAIN_ROWS | 220 | 最小训练样本 |
| CACHE_STALE_DAYS | 10 | 缓存过期天数 |

---

## 14. 前端架构

### 14.1 技术栈

| 类别 | 选型 |
|------|------|
| 框架 | Vue 3 Composition API |
| 构建 | Vite 5 |
| UI库 | Element Plus |
| 图表 | ECharts 5 |
| HTTP | Axios (baseURL=/api/v1) |
| 状态管理 | Pinia |
| 路由 | Vue Router 4 |
| CSS预处理 | Dart SCSS (variables.scss全局主题) |

### 14.2 页面路由

| 路径 | 组件 | 功能 |
|------|------|------|
| `/` | Dashboard.vue | 总览仪表盘 |
| `/predict` | Predict.vue | 单基金预测 |
| `/profile/:code` | Profile.vue | 基金画像 |
| `/train` | Train.vue | 模型训练 |
| `/compare` | Compare.vue | 多基金对比 |
| `/backtest` | Backtest.vue | 历史回测 |
| `/intraday` | Intraday.vue | 日内估计 |
| `/admin/data` | AdminDataStatus.vue | 数据管理 |

### 14.3 前端日志系统

```
logger.js (结构化日志)
  ├─ debug/info/warn/error(level, module, message, data)
  ├─ pagePerformance() → 采集页面加载指标
  ├─ action(action, target) → 用户操作审计
  ├─ getLogs/exportAsJson() → 日志查询和导出
  └─ 远程上报 (可选, 通过 VITE_LOG_REMOTE_URL 配置)

request.js (Axios拦截器)
  ├─ 请求拦截: 记录 method/url/hasData
  ├─ 响应拦截: 提取 X-Request-ID / X-Response-Time-ms
  └─ 错误拦截: 按 status code 分类提示用户

App.vue (错误边界)
  └─ onErrorCaptured: 捕获组件渲染异常, 记录堆栈

vite.config.js (Vite插件)
  ├─ proxy error 事件: 捕获 ECONNREFUSED 等
  ├─ res.writeHead 拦截: 4xx/5xx 状态码记录
  └─ slow request (>500ms) 告警
```

---

## 15. 日志系统

### 15.1 日志文件清单

| 文件 | 格式 | 内容 | 用途 |
|------|------|------|------|
| `logs/app.log` | 文本 | 应用主日志(含上下文) | 开发调试、问题排查 |
| `logs/api.jsonl` | JSONL | 每次HTTP请求一条 | API监控、QPS分析 |
| `logs/train.log` | 文本 | 训练过程(DEBUG级) | 模型迭代追踪 |
| `logs/error.log` | 文本 | ERROR及以上级别 | 错误告警 |
| `logs/audit.jsonl` | JSONL | 用户操作审计 | 合规追溯 |
| `logs/perf.jsonl` | JSONL | 性能指标 | 性能优化 |
| `logs/frontend/dev.log` | 文本 | NPM/Vite生命周期 | 前端运维 |

### 15.2 结构化JSON日志格式

```json
{
  "@timestamp": "2026-05-24T12:00:00Z",
  "level": "INFO",
  "logger": "api.access",
  "message": "api_request",
  "module": "logging_config",
  "function": "_log_api_request",
  "line": 72,
  "thread": "MainThread",
  "request_id": "abc123def456",
  "fund_code": "110011",
  "task_id": "-",
  "stage": "-",
  "extra": {
    "method": "POST",
    "path": "/api/v1/fund/predict",
    "query": "",
    "status_code": 200,
    "elapsed_ms": 152.34,
    "client_ip": "127.0.0.1",
    "error": null
  },
  "exception": null
}
```

### 15.3 上下文传递机制

```python
# 设置 (在请求开始时)
set_log_context(request_id="abc123", fund_code="110011", stage="feature_build")

# 自动附加到每条日志 (通过ContextFilter)
# output: "... | request_id=abc123 | fund_code=110011 | stage=feature_build | ..."
```

---

## 附录A: 异常处理全景

| 异常场景 | 抛出异常 | HTTP状态 | 用户看到的信息 |
|---------|---------|---------|--------------|
| 基金代码不存在 | DataFetchError | 502 | "无法获取基金 XXX 数据" |
| 历史数据不足220行 | InsufficientDataError | 422 | "历史数据不足，需要至少220个交易日" |
| 模型文件不存在 | ModelNotFoundError | 404 | "该基金尚未训练模型" |
| 训练过程中OOM | TrainingError | 500 | "训练失败: 内存不足" |
| 预测值NaN | PredictionError | 500 | "预测计算异常" |
| akshare网络超时 | DataFetchError | 502 | "数据源暂时不可用，已使用缓存" |
| 指数数据缺失 | (不抛异常) | 200 | 该指数列为NaN, 其他特征正常计算 |
| 校准集<20条 | (不抛异常) | 200 | 使用fallback固定宽度区间 |
| VIF矩阵奇异 | (不抛异常) | 200 | 停止VIF剔除, 保留当前特征集 |

---

## 附录B: 性能关键路径

| 操作 | 预期耗时 | 优化措施 |
|------|---------|---------|
| 基金净值加载(缓存命中) | <10ms | 内存缓存 + TTL |
| 指数数据获取(5个并发) | 2-5s | ThreadPoolExecutor(5) |
| 特征构建(~80列) | 50-200ms | pandas向量化运算 |
| 因子预筛选(~80个) | 100-500ms | 只对top20做衰减测试 |
| Walk-Forward CV(12轮) | 5-30s | 取决于数据量和模型复杂度 |
| Stacking集成训练 | 1-5s | 4个基础模型 + Ridge元学习器 |
| 保形预测 | <10ms | 分位数计算O(N) |
| 单次预测推理 | <50ms | 模型已加载到内存 |

---

*文档结束*
