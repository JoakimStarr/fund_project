/**
 * 图表工具 - 基于 ECharts
 */

// 初始化回测图表
function initBacktestChart(containerId, data) {
  const chartDom = document.getElementById(containerId);
  if (!chartDom || !data || !data.rows) return null;
  
  const myChart = echarts.init(chartDom);
  const rows = data.rows;
  
  // 提取数据
  const dates = rows.map(r => r.feature_date || r.date);
  const actual = rows.map(r => r.actual_return || r.target_next);
  const pred = rows.map(r => r.pred_return || r.pred);
  const baseline = rows.map(r => r.baseline || r.rolling_mean_baseline);
  const pUp = rows.map(r => r.p_up);
  
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
      data: ['实际收益', '点预测', '基准', '上涨概率'],
      top: 10
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
      axisLabel: {
        rotate: 45,
        fontSize: 11
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '收益率',
        axisLabel: {
          formatter: (val) => (val * 100).toFixed(0) + '%'
        }
      },
      {
        type: 'value',
        name: '概率',
        min: 0,
        max: 1,
        axisLabel: {
          formatter: (val) => (val * 100).toFixed(0) + '%'
        }
      }
    ],
    series: [
      {
        name: '实际收益',
        type: 'line',
        data: actual,
        lineStyle: { color: '#666', width: 1 },
        itemStyle: { color: '#666' },
        symbol: 'none'
      },
      {
        name: '点预测',
        type: 'line',
        data: pred,
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
        symbol: 'circle',
        symbolSize: 4
      },
      {
        name: '基准',
        type: 'line',
        data: baseline,
        lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' },
        itemStyle: { color: '#94a3b8' },
        symbol: 'none'
      },
      {
        name: '上涨概率',
        type: 'line',
        yAxisIndex: 1,
        data: pUp,
        lineStyle: { color: '#f59e0b', width: 1 },
        itemStyle: { color: '#f59e0b' },
        symbol: 'none',
        areaStyle: {
          color: 'rgba(245, 158, 11, 0.1)'
        }
      }
    ]
  };
  
  myChart.setOption(option);
  return myChart;
}

// 初始化暴露因子条形图
function initExposureChart(containerId, data) {
  const chartDom = document.getElementById(containerId);
  if (!chartDom || !data) return null;
  
  const myChart = echarts.init(chartDom);
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}'
      }
    },
    yAxis: {
      type: 'category',
      data: data.names || [],
      axisLabel: {
        fontSize: 11
      }
    },
    series: [
      {
        name: '暴露值',
        type: 'bar',
        data: data.values || [],
        itemStyle: {
          color: (params) => params.value >= 0 ? '#dc2626' : '#16a34a'
        }
      }
    ]
  };
  
  myChart.setOption(option);
  return myChart;
}

// 初始化简单趋势图
function initTrendChart(containerId, data) {
  const chartDom = document.getElementById(containerId);
  if (!chartDom || !data) return null;
  
  const myChart = echarts.init(chartDom);
  
  const option = {
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.dates || [],
      show: false
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: [
      {
        type: 'line',
        data: data.values || [],
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#2563eb',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(37, 99, 235, 0.3)' },
              { offset: 1, color: 'rgba(37, 99, 235, 0.05)' }
            ]
          }
        }
      }
    ]
  };
  
  myChart.setOption(option);
  return myChart;
}

// 响应式重绘
function handleChartResize(charts) {
  window.addEventListener('resize', () => {
    charts.forEach(chart => {
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  });
}

// 导出图表函数
window.initBacktestChart = initBacktestChart;
window.initExposureChart = initExposureChart;
window.initTrendChart = initTrendChart;
window.handleChartResize = handleChartResize;
