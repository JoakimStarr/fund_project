# 基金预测系统 — 数据架构改造设计方案

> 版本: v1.0 | 日期: 2026-05-24 | 状态: 待评审

---

## 一、现状问题诊断

### 1.1 Profile 数据完全失真

**前端 [Profile.vue](../frontend/src/views/Profile.vue#L218-L258)** 使用硬编码假数据：

| 字段 | 当前值 | 问题 |
|------|--------|------|
| `fundName` | `'财通资管新能源汽车混合A'` | 硬编码死值，不随基金代码变化 |
| `manager` | `'张三'` | **假的基金经理名** |
| `fundSize` | `'52.36亿'` | 固定不变 |
| `riskScore` | `72` | 永远72分 |
| `allocation` | 股票85%/债券8% | 固定比例 |
| `industryDistribution` | 电力设备35%/汽车25%... | 固定行业分布 |

**后端 [`classify_fund()`](../backend/app/services/fund_profile_service.py#L24)** 虽然能从 akshare 获取真实数据：
- 每次调用**实时请求网络**，无任何缓存层
- 失败时静默降级为默认值 `hybrid_equity`
- **数据库中无 `fund_profiles` 表**

### 1.2 数据库几乎为空

当前 SQLite 只有一张表：

```sql
-- database.py 中唯一的表
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    fund_code TEXT NOT NULL,
    status TEXT NOT NULL,
    ...
);
```

缺失的表：`fund_profiles`, `fund_nav`, `index_data`, `holdings`, `train_results`

### 1.3 训练数据全部散落在 CSV 文件

```
data/raw/
├── fund_nav/     ← 5个CSV (净值数据)
├── index/        ← 6个CSV (指数数据)
├── stocks/       ← ~20个CSV (个股数据)
├── holdings/     ← 3个CSV (持仓数据)
└── theme_index/  ← ~12个CSV (主题指数)
```

**问题**：
- 无法增量更新（需重写整个文件）
- 无事务保护（写入中断则文件损坏）
- 无法跨表 JOIN 查询
- 文件数量会随基金数线性增长

---

## 二、目标架构

### 2.1 设计原则

1. **Profile 元数据 → 必须入 SQL**（结构化、需要查询、需要缓存）
2. **时序数据(NAV/指数) → SQL 为主、CSV 为辅**（SQL 负责一致性和增量，CSV 作为训练时的内存映射缓存）
3. **向后兼容** — 改造期间 CSV 读取逻辑保留作为 fallback
4. **渐进式迁移** — 不一次性删除 CSV，先建 DB 层再逐步切换

### 2.2 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      数据层架构                               │
│                                                             │
│  ┌────────────────────┐     ┌──────────────────────────┐   │
│  │   SQLite 主库       │     │   CSV 缓存层              │   │
│  │   (data/fund_       │     │   (data/raw/)             │   │
│  │    predictor.db)    │     │                          │   │
│  │                    │     │                          │   │
│  │ ┌────────────────┐ │     │  训练时可选:              │   │
│  │ │fund_profiles   │ │◄──►│  • read_csv() ← 快速      │   │
│  │ │fund_nav        │ │     │  • read_sql() ← 一致     │   │
│  │ │index_data      │ │     │                          │   │
│  │ │holdings        │ │     │  CSV 作为:                │   │
│  │ │theme_index     │ │     │  • 备份                  │   │
│  │ │train_results   │ │     │  • 离线 fallback         │   │
│  │ │model_registry  │ │     │  • 数据导出              │   │
│  │ └────────────────┘ │     └──────────────────────────┘   │
│  └────────────────────┘                                     │
│                                                             │
│  写入策略:                                                   │
│  • API获取 → 先写DB(带TTL) → 异步同步到CSV                   │
│  • 训练读取 → 优先read_sql → 降级read_csv                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、数据库 Schema 设计

### 3.1 ER 图

```
fund_profiles (1) ─────< (N) fund_nav
      │                        │
      │                        │
      ├── (N) holdings         └─ (N) feature_cache
      │
      └── (N) train_results

index_data (独立实体)
theme_index (独立实体)
```

### 3.2 表定义

#### 表1: `fund_profiles` — 基金画像主表

```sql
CREATE TABLE IF NOT EXISTS fund_profiles (
    fund_code       TEXT PRIMARY KEY,          -- 基金代码(6位)
    fund_name       TEXT NOT NULL DEFAULT '',  -- 基金简称
    fund_type       TEXT NOT NULL DEFAULT 'unknown', -- 标准化分类标签
    fund_type_raw   TEXT DEFAULT '',           -- 原始类型字符串(来自API)

    -- 基本信息
    establish_date  TEXT,                      -- 成立日期
    fund_size       REAL,                      -- 最新规模(亿元)
    manager         TEXT DEFAULT '',            -- 基金经理
    fee_rate        REAL,                      -- 管理费率

    -- 投资信息
    benchmark       TEXT DEFAULT '',            -- 业绩比较基准
    strategy_text   TEXT DEFAULT '',            -- 投资策略原文
    strategy_keywords TEXT DEFAULT '',          -- JSON数组: ["成长","价值",...]

    -- 分类判定结果
    skip_prediction INTEGER DEFAULT 0,          -- 是否跳过预测(货币基金=1)
    risk_level      TEXT DEFAULT '',            -- 风险等级评估

    -- 数据来源与缓存
    data_source     TEXT DEFAULT 'akshare',    -- 数据来源
    fetched_at      TEXT NOT NULL,              -- 获取时间(ISO8601)
    updated_at      TEXT NOT NULL,              -- 更新时间(ISO8601)
    cache_ttl_days  INTEGER DEFAULT 7,          -- 缓存有效期(天)
    raw_info_json   TEXT DEFAULT ''             -- 原始API返回JSON(用于调试)
);

-- 索引: 按类型和名称查询
CREATE INDEX IF NOT EXISTS idx_fund_profiles_type ON fund_profiles(fund_type);
CREATE INDEX IF NOT EXISTS idx_fund_profiles_name ON fund_profiles(fund_name);
```

#### 表2: `fund_nav` — 基金净值时序

```sql
CREATE TABLE IF NOT EXISTS fund_nav (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       TEXT NOT NULL,              -- 基金代码
    trade_date      TEXT NOT NULL,              -- 交易日期(YYYY-MM-DD)
    nav             REAL NOT NULL,               -- 单位净值
    acc_nav         REAL,                       -- 累计净值
    daily_growth_pct REAL,                      -- 日增长率(%)
    source          TEXT DEFAULT 'unknown',      -- 数据来源

    FOREIGN KEY (fund_code) REFERENCES fund_profiles(fund_code),
    UNIQUE(fund_code, trade_date)               -- 同一基金同一天唯一
);

-- 索引: 时序查询核心
CREATE INDEX IF NOT EXISTS idx_fund_nav_code_date ON fund_nav(fund_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_fund_nav_date ON fund_nav(trade_date);
```

#### 表3: `index_data` — 指数行情时序

```sql
CREATE TABLE IF NOT EXISTS index_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name      TEXT NOT NULL,              -- 指数名称(hs300/zz500等)
    symbol          TEXT NOT NULL,              -- 交易代码(sh000300等)
    trade_date      TEXT NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL NOT NULL,
    volume          REAL,
    amount          REAL,
    source          TEXT DEFAULT 'eastmoney',

    UNIQUE(index_name, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_index_data_name_date ON index_data(index_name, trade_date);
```

#### 表4: `holdings` — 基金持仓快照

```sql
CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       TEXT NOT NULL,
    report_date     TEXT NOT NULL,              -- 报告期(季度末)
    stock_code      TEXT NOT NULL,              -- 股票代码
    stock_name      TEXT DEFAULT '',
    weight_pct      REAL,                       -- 占净值比(%)
    market_cap      REAL,                       -- 市值(亿元)
    sector          TEXT DEFAULT '',            -- 所属行业

    UNIQUE(fund_code, report_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_holdings_fund_date ON holdings(fund_code, report_date);
```

#### 表5: `train_results` — 训练结果归档

```sql
CREATE TABLE IF NOT EXISTS train_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL UNIQUE,
    fund_code       TEXT NOT NULL,
    model_version   TEXT DEFAULT '',
    model_type      TEXT DEFAULT '',             -- point/direction

    -- 性能指标(JSON)
    metrics_json    TEXT DEFAULT '',

    -- 选中的特征列(JSON数组)
    features_json   TEXT DEFAULT '',

    -- 模型文件路径(pickle/joblib)
    model_path      TEXT DEFAULT '',

    -- 回测数据引用
    backtest_path   TEXT DEFAULT '',

    status          TEXT DEFAULT 'success',
    created_at      TEXT NOT NULL,
    training_duration_secs REAL,

    FOREIGN KEY (fund_code) REFERENCES fund_profiles(fund_code)
);

CREATE INDEX IF NOT EXISTS idx_train_results_fund ON train_results(fund_code);
CREATE INDEX IF NOT EXISTS idx_train_results_created ON train_results(created_at);
```

#### 表6: `data_fetch_log` — 数据获取日志(用于调试和监控)

```sql
CREATE TABLE IF NOT EXISTS data_fetch_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL,               -- 'fund_nav'/'index'/'profile'
    entity_key      TEXT NOT NULL,               -- fund_code 或 index_name
    source          TEXT NOT NULL,
    success         INTEGER NOT NULL DEFAULT 0,  -- 0=失败 1=成功
    rows_affected   INTEGER DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER,
    fetched_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fetch_log_entity ON data_fetch_log(entity_type, entity_key, fetched_at);
```

---

## 四、数据流设计

### 4.1 Profile 数据流（改造重点）

```
┌──────────┐    GET /api/v1/funds/{code}/profile    ┌───────────┐
│  前端     │ ─────────────────────────────────────→ │  后端API  │
│ Profile  │                                        │           │
│  页面    │ ←───────────────────────────────────── │           │
└──────────┘    返回真实 profile JSON               └─────┬─────┘
                                                       │
                                              ┌────────▼────────┐
                                              │  cache_or_fetch │
                                              │  (新增服务)      │
                                              └────────┬────────┘
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    │                  │                  │
                              ┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐
                              │  DB命中?  │    │  TTL有效?   │   │  调akshare  │
                              │  返回数据  │    │  返回数据   │   │  获取+入库  │
                              └───────────┘    └─────────────┘   └─────────────┘
```

**核心逻辑伪代码**：

```python
def get_profile(fund_code: str) -> FundProfile:
    # 1. 查数据库
    row = db_query("SELECT * FROM fund_profiles WHERE fund_code=?", [fund_code])

    if row and _is_fresh(row["fetched_at"], row["cache_ttl_days"]):
        return _row_to_profile(row)  # 缓存命中

    # 2. 缓存未命中或过期 → 从API获取
    try:
        info = ak.fund_individual_basic_info_xq(symbol=fund_code)
        profile = _parse_and_classify(info)

        # 3. UPSERT 到数据库
        db_execute("""
            INSERT INTO fund_profiles (...) VALUES (...)
            ON CONFLICT(fund_code) DO UPDATE SET
                fund_name=excluded.fund_name, ..., fetched_at=datetime('now')
        """, _profile_to_row(profile))

        # 4. 记录获取日志
        log_fetch("profile", fund_code, "akshare", success=True)

        return profile
    except Exception as e:
        # 5. 失败但有旧缓存 → 降级返回旧数据(标记stale)
        if row:
            return _row_to_profile(row) | {"stale": True}
        raise
```

### 4.2 NAV / 指数数据流（增量更新）

```
定时任务 / 手动触发
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  获取最新数据 │────→│  与DB对比    │────→│  INSERT新行   │
│  (最近N天)    │     │  找出增量    │     │  UPDATE变更  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                            可选: 同步到CSV
```

**增量更新策略**：
```python
def sync_fund_nav(fund_code: str):
    # 1. 从API获取全量(或最近365天)
    df_new = fetch_from_api(fund_code)

    # 2. 查询DB中已有数据的最大日期
    last_date = db_scalar("""
        SELECT MAX(trade_date) FROM fund_nav WHERE fund_code=?
    """, [fund_code])

    # 3. 只插入比last_date更新的行
    df_increment = df_new[df_new["date"] > last_date]
    if len(df_increment) > 0:
        df_increment.to_sql("fund_nav", conn, if_exists="append", index=False)

    # 4. 可选: 导出完整CSV作为备份
    df_full = pd.read_sql("SELECT * FROM fund_nav WHERE fund_code=? ORDER BY date", conn)
    df_full.to_csv(RAW_DIR / "fund_nav" / f"{fund_code}.csv", index=False)
```

### 4.3 训练数据读取流

```python
def load_training_data(fund_code: str, use_db: bool = True) -> pd.DataFrame:
    if use_db:
        try:
            nav = pd.read_sql(
                "SELECT * FROM fund_nav WHERE fund_code=? ORDER BY trade_date",
                conn, params=[fund_code]
            )
            indexes = {}
            for name in INDEX_SYMBOLS:
                indexes[name] = pd.read_sql(
                    "SELECT date as trade_date, close, volume FROM index_data WHERE index_name=? ORDER BY trade_date",
                    conn, params=[name]
                )
            return merge_data(nav, indexes)
        except Exception:
            logger.warning("db_read_failed, falling back to csv")
            return load_from_csv(fund_code)  # 降级到CSV
    else:
        return load_from_csv(fund_code)
```

---

## 五、接口变更

### 5.1 新增/修改的 API

| 方法 | 路径 | 变更类型 | 说明 |
|------|------|---------|------|
| `GET` | `/api/v1/funds/{code}/profile` | **修改** | 返回真实DB数据，增加 `stale`/`cached_at` 字段 |
| `GET` | `/api/v1/funds/{code}/nav` | **修改** | 支持 `?source=db\|csv` 参数 |
| `POST` | `/api/v1/admin/sync/{code}` | **新增** | 手动触发单只基金数据同步 |
| `POST` | `/api/v1/admin/sync/all` | **新增** | 全量数据同步(后台任务) |
| `GET` | `/api/v1/admin/data-status` | **新增** | 返回各表的行数、最新日期、缓存状态 |
| `DELETE` | `/api/v1/admin/cache/{code}` | **新增** | 清除指定基金的缓存，强制重新获取 |

### 5.2 Profile API 响应格式（新）

```json
{
  "fund_code": "022771",
  "fund_name": "前海开源沪港深创新成长混合A",
  "fund_type": "hybrid_equity",
  "fund_type_raw": "混合型-偏股",
  "establish_date": "2019-02-14",
  "fund_size": 28.57,
  "manager": "王霞,曲扬",
  "fee_rate": 1.50,
  "benchmark": "沪深300指数收益率×70%+中债综合财富(总值)指数收益率×30%",
  "strategy_keywords": ["成长", "科技", "消费"],
  "strategy_text": "本基金在控制风险的前提下...",
  "skip_prediction": false,
  "risk_level": "中高风险",

  "cache_info": {
    "cached": true,
    "fetched_at": "2026-05-24T15:30:00Z",
    "expires_at": "2026-05-31T15:30:00Z",
    "ttl_days": 7,
    "data_source": "akshare",
    "stale": false
  }
}
```

---

## 六、前端改动范围

### 6.1 Profile.vue 改动清单

| 区域 | 当前状态 | 目标状态 |
|------|---------|---------|
| `profileData` 初始化 | 硬编码假数据 (L218-258) | 空对象 `{}`，由 API 响应填充 |
| `loadProfile()` | 调用 API 但不更新显示数据 | 用 `res.data` 完整替换 `profileData.value` |
| 基金名称 | 固定 `"财通资管新能源汽车混合A"` | `res.data.fund_name` |
| 经理姓名 | 固定 `"张三"` | `res.data.manager` |
| 规模 | 固定 `"52.36亿"` | 格式化 `res.data.fund_size` + `"亿"` |
| 风险评分 | 固定 `72` | 根据 `fund_type` 映射到风险分 (或从API获取) |
| 资产配置饼图 | 固定 85/8/5/2 | 从 holdings 表聚合计算 |
| 行业分布柱状图 | 固定 6个行业 | 从 holdings 表按 sector 聚合 |
| 策略关键词 | 固定新能源相关 | `res.data.strategy_keywords` |
| 业绩比较基准 | 固定沪深300*70%+中债*30% | `res.data.benchmark` |

### 6.2 新增字段映射

```
API响应字段              →    前端展示位置
─────────────────────────────────────────
fund_name               →    h2.fund-name
fund_type               →    el-tag (typeTagType 映射)
fund_size               →    metric-value "规模"
establish_date          →    metric-value "成立日期"
manager                 →    metric-value "基金经理"
benchmark               →    benchmark-info .value
strategy_keywords       →    el-tag 循环渲染
strategy_text           →    strategy-description
skip_prediction         →    predictionSuitable 布尔值
cache_info.stale        →    显示"数据可能过期"警告badge
```

---

## 七、SQL vs CSV 决策矩阵

### 7.1 各数据类型的推荐存储方式

| 数据特征 | 推荐存储 | 理由 |
|---------|---------|------|
| **Profile元数据** | ✅ **SQL必选** | 结构化行、频繁查询、需要UPSERT、需要TTL缓存 |
| **NAV时序**(单基金~1000行) | 🥇 SQL + 🥈 CSV备份 | 需要增量更新、日期范围查询、JOIN指数数据 |
| **指数时序**(单个~5000行) | 🥇 SQL + 🥈 CSV备份 | 同上，且多基金共享同一份指数数据 |
| **持仓快照**(每季度~10行) | ✅ **SQL必选** | 低频更新、需要聚合分析(行业分布/集中度) |
| **训练中间特征矩阵** | 💾 临时文件/内存 | 一次性使用、大矩阵(~1000×200)、无需持久化 |
| **模型序列化文件** | 💾 文件系统(joblib) | 二进制大对象，不适合放DB |
| **回测结果DataFrame** | ✅ SQL(train_results表) | 需要历史对比、版本追踪 |

### 7.2 为什么不完全放弃 CSV？

1. **pandas `read_csv` 比 `read_sql` 快 5-10倍** — 对于每次训练都全量加载的场景，CSV 有性能优势
2. **离线分析友好** — 可以直接用 Excel/Python 打开查看
3. **Docker 卷挂载方便** — 数据目录可以单独挂载备份
4. **降级方案** — DB 故障时可切换到 CSV 模式继续运行

**结论**: CSV 作为"热缓存"层保留，SQL 作为"权威源"和"增量更新"层。

---

## 八、实施计划

### Phase 1: Profile 数据修复 (P0 — 本次实施)

- [ ] 扩展 `database.py` Schema（新增 6 张表）
- [ ] 实现 `profile_service.py` 的 DB 缓存层
- [ ] 新增 `/api/v1/funds/{code}/profile` 返回真实数据
- [ ] 重写 `Profile.vue` 使用 API 数据替代硬编码
- [ ] 新增 admin 数据管理 API

### Phase 2: NAV/指数数据入DB (P1)

- [ ] 实现 `data_service.py` 的双写逻辑（DB + CSV）
- [ ] 实现增量更新（只追加新行）
- [ ] 训练读取支持 `use_db` 参数
- [ ] 数据同步状态 API

### Phase 3: 持仓与分析增强 (P2)

- [ ] holdings 数据入库
- [ ] 前端行业分布/资产配置图表改为实时聚合
- [ ] 持仓变动追踪

### Phase 4: 清理与优化 (P3)

- [ ] 移除不再需要的硬编码数据
- [ ] CSV 文件改为纯缓存（可随时重建）
- [ ] 数据健康检查定时任务

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| akshare API 限频/封禁 | Profile 获取失败 | DB 缓存 7 天 TTL，减少调用频率；失败时返回 stale 缓存 |
| SQLite 并发写锁竞争 | 训练同时写入时变慢 | WAL 模式已开启；写入操作异步化 |
| Schema 变更导致旧数据不兼容 | 升级后启动失败 | `_init_schema` 做 ALTER TABLE 兼容升级；备份数据 |
| 前端改坏 Profile 页面样式 | 用户看到空白/错乱 | 保留 mock 数据作为 default value兜底 |
