/**
 * Quant Dashboard - 回测诊断页面逻辑
 */

let backtestChart = null;

function initBacktest() {
  highlightNav('backtest');
  const code = getFundCodeFromUrl();
  setFundCode(code);
  $('loadBtn')?.addEventListener('click', loadBacktestData);
  if (code) loadBacktestData();
}

async function loadBacktestData() {
  const code = getFundCode();
  if (!code) return;
  setFundCodeInUrl(code);
  setLoading(['loadBtn'], true);
  try {
    const backtestRes = await fetchBacktest(code);
    renderBacktest(backtestRes);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(['loadBtn'], false);
  }
}

function renderBacktest(data) {
  if (!data || !data.rows) {
    show('emptyState');
    hide('resultSection');
    return;
  }
  hide('emptyState');
  show('resultSection');

  const rows = data.rows;
  const metrics = data.metrics || {};

  // 销毁旧图表
  if (backtestChart) {
    backtestChart.dispose();
  }

  // 初始化 ECharts
  backtestChart = echarts.init($('backtestChart'));

  const dates = rows.map(r => r.feature_date || r.date);
  const actual = rows.map(r => r.actual_return || r.target_next);
  const pred = rows.map(r => r.pred_return || r.pred);
  const baseline = rows.map(r => r.baseline || r.rolling_mean_baseline);

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        const idx = params[0].dataIndex;
        const row = rows[idx];
        let html = `<div style="font-weight:bold;margin-bottom:5px">${dates[idx]}</div>`;
        html += `<div>特征日期: ${row.feature_date || row.date}</div>`;
        html += `<div>目标日期: ${row.target_date || '-'}</div>`;
        html += `<div style="margin-top:5px">`;
        params.forEach(p => {
          const val = p.value !== null && p.value !== undefined ? (p.value * 100).toFixed(2) + '%' : '-';
          html += `<div>${p.marker} ${p.seriesName}: <strong>${val}</strong></div>`;
        });
        html += `</div>`;
        return html;
      }
    },
    legend: {
      data: ['实际收益', '点预测', '基准'],
      top: 10,
      textStyle: { color: '#94a3b8' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#64748b', rotate: 45 },
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: {
      type: 'value',
      name: '收益率',
      nameTextStyle: { color: '#94a3b8' },
      axisLabel: {
        color: '#64748b',
        formatter: (val) => (val * 100).toFixed(0) + '%'
      },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [
      {
        name: '实际收益',
        type: 'line',
        data: actual,
        lineStyle: { color: '#94a3b8', width: 1 },
        itemStyle: { color: '#94a3b8' },
        symbol: 'none'
      },
      {
        name: '点预测',
        type: 'line',
        data: pred,
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
        symbol: 'circle',
        symbolSize: 4
      },
      {
        name: '基准',
        type: 'line',
        data: baseline,
        lineStyle: { color: '#475569', width: 1, type: 'dashed' },
        itemStyle: { color: '#475569' },
        symbol: 'none'
      }
    ]
  };

  backtestChart.setOption(option);

  // 指标
  $('rmse').textContent = metrics.rmse !== undefined ? (metrics.rmse * 100).toFixed(2) + '%' : '-';
  $('mae').textContent = metrics.mae !== undefined ? (metrics.mae * 100).toFixed(2) + '%' : '-';
  $('auc').textContent = metrics.auc !== undefined ? metrics.auc.toFixed(3) : '-';

  // 响应式
  window.addEventListener('resize', () => backtestChart?.resize());

  animateCards('.metric-item', 100);
}

document.addEventListener('DOMContentLoaded', initBacktest);
