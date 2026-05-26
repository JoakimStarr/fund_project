TASK_STATUSES = {"pending", "running", "success", "failed"}

# prediction_history 表（用于残差修正）
"""
CREATE TABLE IF NOT EXISTS prediction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code TEXT NOT NULL,
    predicted_at TEXT NOT NULL,  -- ISO date
    predicted_return REAL NOT NULL,
    actual_return REAL,          -- T+1 实际收益率(滞后填充)
    error REAL,                  # predicted - actual
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(fund_code, predicted_at)
);
"""

# ====================================================
# ★ AI 分析缓存表（v2.6.0 新增）
# ====================================================
"""
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
"""
