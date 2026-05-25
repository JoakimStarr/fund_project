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
