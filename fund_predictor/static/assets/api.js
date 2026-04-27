/**
 * Quant Dashboard - API 接口封装
 */

const API_BASE = '/api';

// 通用请求封装
async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    const err = new Error(data.message || `HTTP ${res.status}`);
    err.code = data.code || 'UNKNOWN_ERROR';
    err.details = data.details || {};
    throw err;
  }
  return data;
}

// 获取预测结果
async function fetchPrediction(fundCode, forceRetrain = false) {
  return api(`${API_BASE}/fund/predict`, {
    method: 'POST',
    body: JSON.stringify({ fund_code: fundCode, force_retrain: forceRetrain }),
  });
}

// 开始训练任务
async function startTraining(fundCode, force = true) {
  return api(`${API_BASE}/train`, {
    method: 'POST',
    body: JSON.stringify({ fund_code: fundCode, force }),
  });
}

// 获取任务状态
async function fetchTaskStatus(taskId) {
  return api(`${API_BASE}/tasks/${taskId}`);
}

// 获取模型信息
async function fetchModelInfo(fundCode) {
  try {
    return api(`${API_BASE}/fund/${fundCode}/model`);
  } catch (e) {
    return null;
  }
}

// 获取回测数据
async function fetchBacktest(fundCode) {
  try {
    return api(`${API_BASE}/fund/${fundCode}/backtest`);
  } catch (e) {
    return null;
  }
}

// 导出API函数
window.api = api;
window.fetchPrediction = fetchPrediction;
window.startTraining = startTraining;
window.fetchTaskStatus = fetchTaskStatus;
window.fetchModelInfo = fetchModelInfo;
window.fetchBacktest = fetchBacktest;
