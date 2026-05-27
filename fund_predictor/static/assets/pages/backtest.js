/**
 * 回测与趋势诊断页面
 */

let backtestChart = null;

function initBacktest() {
  highlightNav('backtest');
  
  const code = getFundCodeFromUrl();
  setFundCode(code);
  
  $('loadBtn')?.addEventListener('click', loadBacktestData);
  
  if (code) {
    loadBacktestData();
  }
}

async function loadBacktestData() {
  const code = getFundCode();
  if (!code) return;
  
  setFundCodeInUrl(code);
  setBusy(['loadBtn'], true);
  
  try {
    const backtestRes = await fetchBacktest(code);
    const modelRes = await fetchModelInfo(code);
    
    renderBacktest(backtestRes, modelRes);
  } catch (err) {
    showError('加载失败: ' + err.message);
  } finally {
    setBusy(['loadBtn'], false);
  }
}

function renderBacktest(backtestData, modelData) {
  if (!backtestData || !backtestData.rows) {
    show('emptyState');
    hide('backtestContent');
    return;
  }
  
  hide('emptyState');
  show('backtestContent');
  
  const rows = backtestData.rows;
  const metrics = backtestData.metrics || {};
  
  // 渲染回测图
  if (backtestChart) {
    backtestChart.dispose();
  }
  backtestChart = initBacktestChart('backtestChart', backtestData);
  
  // 核心指标
  $('rmse').textContent = metrics.rmse !== undefined ? formatBp(metrics.rmse) : '-';
  $('mae').textContent = metrics.mae !== undefined ? formatBp(metrics.mae) : '-';
  $('p90Ae').textContent = metrics.p90_ae !== undefined ? formatBp(metrics.p90_ae) : '-';
  
  // Coverage
  $('coverage70').textContent = metrics.coverage_70 !== undefined ? formatPct(metrics.coverage_70) : '-';
  $('coverage80').textContent = metrics.coverage_80 !== undefined ? formatPct(metrics.coverage_80) : '-';
  $('coverage90').textContent = metrics.coverage_90 !== undefined ? formatPct(metrics.coverage_90) : '-';
  
  // Width
  $('width70').textContent = metrics.width_70_bp !== undefined ? formatBp(metrics.width_70_bp / 10000) : '-';
  $('width80').textContent = metrics.width_80_bp !== undefined ? formatBp(metrics.width_80_bp / 10000) : '-';
  $('width90').textContent = metrics.width_90_bp !== undefined ? formatBp(metrics.width_90_bp / 10000) : '-';
  
  // Lead-Lag 诊断
  const leadLag = modelData?.lead_lag_diagnostics || {};
  renderLeadLagDiagnostics(leadLag);
  
  // 拐点诊断
  const turning = modelData?.turning_point_diagnostics || {};
  renderTurningDiagnostics(turning);
  
  // 响应式
  handleChartResize([backtestChart]);
}

function renderLeadLagDiagnostics(data) {
  const container = $('leadLagDiagnostics');
  if (!container) return;
  
  if (data.error) {
    container.innerHTML = `<div class="error-text">${data.error}</div>`;
    return;
  }
  
  const items = [
    { label: 'Lag -2', value: data.corr_lag_minus_2, desc: '预测 vs 历史' },
    { label: 'Lag -1', value: data.corr_lag_minus_1, desc: '预测 vs 历史' },
    { label: 'Lag 0', value: data.corr_lag_0, desc: '预测 vs 同期' },
    { label: 'Lag +1', value: data.corr_lag_plus_1, desc: '预测 vs 未来' },
    { label: 'Lag +2', value: data.corr_lag_plus_2, desc: '预测 vs 未来' },
  ];
  
  container.innerHTML = items.map(item => `
    <div class="lag-item">
      <div class="lag-label">${item.label}</div>
      <div class="lag-value">${item.value !== undefined ? item.value.toFixed(3) : '-'}</div>
      <div class="lag-desc">${item.desc}</div>
    </div>
  `).join('');
  
  // 最佳滞后和解释
  if (data.best_lag) {
    container.innerHTML += `
      <div class="lag-summary">
        <div>最佳滞后: <strong>Lag ${data.best_lag}</strong> (r=${data.best_lag_corr?.toFixed(3) || '-'})</div>
        <div class="lag-interpretation">${data.interpretation || ''}</div>
      </div>
    `;
  }
}

function renderTurningDiagnostics(data) {
  const container = $('turningDiagnostics');
  if (!container) return;
  
  if (data.error) {
    container.innerHTML = `<div class="error-text">${data.error}</div>`;
    return;
  }
  
  container.innerHTML = `
    <div class="turning-grid">
      <div class="turning-item">
        <div class="turning-label">提前1天命中率</div>
        <div class="turning-value">${data.one_day_early_turn_hit_rate !== undefined ? formatPct(data.one_day_early_turn_hit_rate) : '-'}</div>
      </div>
      <div class="turning-item">
        <div class="turning-label">当天命中率</div>
        <div class="turning-value">${data.same_day_turn_hit_rate !== undefined ? formatPct(data.same_day_turn_hit_rate) : '-'}</div>
      </div>
      <div class="turning-item">
        <div class="turning-label">滞后1天命中率</div>
        <div class="turning-value">${data.one_day_late_turn_hit_rate !== undefined ? formatPct(data.one_day_late_turn_hit_rate) : '-'}</div>
      </div>
    </div>
    <div class="turning-summary">
      <div>拐点数量: ${data.turning_point_count || 0}</div>
      <div class="turning-interpretation">${data.interpretation || ''}</div>
    </div>
  `;
}

document.addEventListener('DOMContentLoaded', initBacktest);
