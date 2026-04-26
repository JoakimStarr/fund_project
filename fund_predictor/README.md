# 基金 T+1 净值涨跌幅区间预测系统

本项目是一个本地运行的基金预测实验系统。用户输入基金代码后，系统读取或下载基金历史净值与市场指数行情，构造默认特征池，完成特征筛选、模型选择、回测和模型持久化，并输出下一交易日基金收益率预测中位数和 90% 预测区间。

本系统不做实时盘中预测，不承诺收益。

## 安装与启动

Windows 双击：

```bat
start.bat
```

脚本会自动创建 `.venv`、安装依赖、启动 FastAPI，并打开：

```text
http://127.0.0.1:8000
```

手动启动：

```bat
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## API

`POST /api/fund/predict`

```json
{"fund_code":"018956","force_retrain":false}
```

`POST /api/train`

```json
{"fund_code":"018956","force":true}
```

`GET /api/tasks/{task_id}`

`GET /api/fund/{fund_code}/model`

`GET /api/fund/{fund_code}/backtest`

错误统一返回：

```json
{
  "ok": false,
  "error": {
    "code": "DATA_FETCH_FAILED",
    "message": "...",
    "stage": "data_fetch",
    "request_id": "...",
    "task_id": "...",
    "details": {}
  }
}
```

## 目录结构

```text
fund_predictor/
  backend/app/
  static/
  data/raw/
  data/processed/
  models/
  logs/
  output/
```

## 常见错误

`DATA_FETCH_FAILED`：基金净值或指数行情下载失败。检查网络和 `logs/error.log`。

`DATA_STALE`：本地缓存数据过旧，且本次要求使用最新数据。

`MODEL_NOT_FOUND`：该基金还没有模型档案，请点击“训练并预测”。

`INSUFFICIENT_DATA`：可训练样本不足，无法完成模型选择。

`MODEL_SELECTION_FAILED`：没有候选模型成功通过筛选或测试。

## 日志位置

日志统一使用 `logging.config.dictConfig` 配置：

- `logs/app.log`
- `logs/train.log`
- `logs/error.log`

日志包含 timestamp、level、logger_name、request_id、fund_code、task_id、stage、message 和异常 traceback。

## 模型文件位置

每只基金保存到：

```text
models/{fund_code}/
  model.pkl
  config.json
  metrics.json
  selected_features.json
  backtest.csv
  prediction_history.csv
```

`model.pkl` 保存完整 scikit-learn Pipeline。

## 免责声明

本系统仅用于量化研究和模型实验，不构成任何投资建议。预测结果可能失效，用户不应据此直接进行交易决策。
