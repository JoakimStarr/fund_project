/**
 * 资产暴露页面
 */

function initExposure() {
  highlightNav('exposure');
  
  const code = getFundCodeFromUrl();
  setFundCode(code);
  
  $('loadBtn')?.addEventListener('click', loadExposureData);
  
  if (code) {
    loadExposureData();
  }
}

async function loadExposureData() {
  const code = getFundCode();
  if (!code) return;
  
  setFundCodeInUrl(code);
  setBusy(['loadBtn'], true);
  
  try {
    // 获取预测数据（包含proxy信息）
    const predRes = await fetchPrediction(code, false);
    const data = predRes.data;
    
    renderExposure(data);
  } catch (err) {
    showError('加载失败: ' + err.message);
  } finally {
    setBusy(['loadBtn'], false);
  }
}

function renderExposure(data) {
  if (!data) return;
  
  // Top10状态
  const top10Status = data.top10_proxy_status || 'unavailable';
  const statusText = {
    'usable': '可用',
    'partial': '部分可用',
    'unavailable': '不可用'
  }[top10Status] || '未知';
  
  $('top10Status').textContent = statusText;
  $('top10Status').className = `status-badge ${top10Status}`;
  
  // 成功/缺失数量
  $('availableCount').textContent = data.top10_proxy_available_count || 0;
  $('missingCount').textContent = data.top10_proxy_missing_count || 0;
  
  // 持仓报告日期
  $('holdingReportDate').textContent = data.holding_report_date || '-';
  
  // Proxy R2 和 Tracking Error
  $('proxyR2').textContent = data.proxy_r2_60 !== undefined ? data.proxy_r2_60.toFixed(3) : '-';
  $('trackingError').textContent = data.tracking_error_60 !== undefined ? (data.tracking_error_60 * 100).toFixed(2) + '%' : '-';
  
  // 解释力等级
  const r2 = data.proxy_r2_60 || 0;
  let explanatoryLevel = '弱';
  if (r2 > 0.7) explanatoryLevel = '强';
  else if (r2 > 0.4) explanatoryLevel = '中等';
  $('explanatoryLevel').textContent = explanatoryLevel;
  
  // Top10股票表
  const stockList = data.top10_stocks || [];
  const stockTable = $('stockTable');
  if (stockTable) {
    if (stockList.length > 0) {
      stockTable.innerHTML = stockList.map(stock => `
        <tr>
          <td>${stock.code || '-'}</td>
          <td>${stock.name || '-'}</td>
          <td>${stock.weight !== undefined ? (stock.weight * 100).toFixed(2) + '%' : '-'}</td>
          <td>${stock.status || '-'}</td>
        </tr>
      `).join('');
    } else {
      stockTable.innerHTML = '<tr><td colspan="4" class="empty-text">暂无股票数据</td></tr>';
    }
  }
  
  // 暴露因子条形图
  const exposures = data.top_exposures || [];
  if (exposures.length > 0 && $('exposureChart')) {
    const chartData = {
      names: exposures.map(e => e.name),
      values: exposures.map(e => e.beta)
    };
    initExposureChart('exposureChart', chartData);
  }
  
  // 数据源详情
  const sources = data.stock_sources_used || {};
  const sourcesList = Object.entries(sources).map(([code, source]) => 
    `<div class="source-item">${code}: ${source}</div>`
  ).join('');
  $('dataSources').innerHTML = sourcesList || '<div class="empty-text">暂无数据源信息</div>';
  
  // 持仓穿越风险提示
  const hasLookaheadRisk = data.holding_lookahead_risk || false;
  $('lookaheadRisk').textContent = hasLookaheadRisk ? 
    '⚠️ 当前使用最新持仓报告，历史回测存在持仓穿越风险' : 
    '✓ 持仓数据无穿越风险';
  $('lookaheadRisk').className = hasLookaheadRisk ? 'risk-warning' : 'risk-ok';
  
  // 主题代理质量提示
  const themeCount = data.theme_available_count || 0;
  $('themeQuality').textContent = themeCount > 0 ? 
    `主题代理可用 (${themeCount}个)` : 
    '主题代理暂不可用';
}

document.addEventListener('DOMContentLoaded', initExposure);
