/**
 * Quant Dashboard - 资产暴露页面逻辑
 */

function initExposure() {
  highlightNav('exposure');
  const code = getFundCodeFromUrl();
  setFundCode(code);
  $('loadBtn')?.addEventListener('click', loadExposureData);
  if (code) loadExposureData();
}

async function loadExposureData() {
  const code = getFundCode();
  if (!code) return;
  setFundCodeInUrl(code);
  setLoading(['loadBtn'], true);
  try {
    const res = await fetchPrediction(code, false);
    renderExposure(res.data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(['loadBtn'], false);
  }
}

function renderExposure(data) {
  if (!data) return;
  hide('emptyState');
  show('resultSection');
  
  const status = data.top10_proxy_status || 'unavailable';
  const statusText = { usable: '可用', partial: '部分', unavailable: '不可用' }[status] || '未知';
  $('top10Status').textContent = statusText;
  
  const r2 = data.proxy_r2_60;
  $('proxyR2').textContent = r2 !== undefined ? r2.toFixed(3) : '-';
  
  const te = data.tracking_error_60;
  $('trackingError').textContent = te !== undefined ? (te * 100).toFixed(2) + '%' : '-';
  
  const hasRisk = data.holding_lookahead_risk || false;
  $('riskWarning').textContent = hasRisk 
    ? '⚠️ 当前使用最新持仓报告，历史回测存在持仓穿越风险' 
    : '✓ 无持仓穿越风险';
  
  animateCards('.metric-item', 100);
}

document.addEventListener('DOMContentLoaded', initExposure);
