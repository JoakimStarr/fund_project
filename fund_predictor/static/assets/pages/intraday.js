/**
 * 今日估值 / 盘中跟踪页面
 */

function initIntraday() {
  highlightNav('intraday');
  
  const code = getFundCodeFromUrl();
  setFundCode(code);
  
  // 显示预留状态
  renderIntradayPlaceholder();
}

function renderIntradayPlaceholder() {
  // 所有数据占位
  const placeholder = '盘中估值模块尚未启用';
  
  const elements = [
    'lastNavDate', 'lastNav', 'latestQuoteTime',
    'estimatedReturn', 'estimatedNav', 'dataCompleteness'
  ];
  
  elements.forEach(id => {
    const el = $(id);
    if (el) el.textContent = placeholder;
  });
  
  // Top10贡献表占位
  const top10Table = $('top10Contribution');
  if (top10Table) {
    top10Table.innerHTML = `
      <tr><td colspan="4" class="placeholder-text">${placeholder}</td></tr>
    `;
  }
  
  // 主题代理贡献表占位
  const themeTable = $('themeContribution');
  if (themeTable) {
    themeTable.innerHTML = `
      <tr><td colspan="4" class="placeholder-text">${placeholder}</td></tr>
    `;
  }
}

document.addEventListener('DOMContentLoaded', initIntraday);
