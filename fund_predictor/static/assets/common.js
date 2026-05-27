/**
 * Quant Dashboard - 公共工具函数
 * 数字滚动、卡片动画、DOM工具
 */

// DOM 选择器
const $ = (id) => document.getElementById(id);
const $$ = (selector) => document.querySelectorAll(selector);

// 数字格式化
function formatNumber(num, digits = 2) {
  const n = Number(num);
  return Number.isFinite(n) ? n.toFixed(digits) : '-';
}

// 百分比格式化
function formatPct(value, digits = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  const sign = num > 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(digits)}%`;
}

// 带符号百分比（中文习惯）
function formatSignedPctCN(value, digits = 2) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  const sign = num > 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(digits)}%`;
}

// 获取涨跌样式类（A股习惯：红涨绿跌）
function getReturnClass(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return 'neutral';
  return num > 0 ? 'positive' : 'negative';
}

// 数字滚动动画
function animateNumber(element, targetValue, duration = 1000, suffix = '') {
  if (!element) return;
  
  const target = Number(targetValue);
  if (!Number.isFinite(target)) {
    element.textContent = '-';
    return;
  }
  
  const startTime = performance.now();
  const startValue = 0;
  
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // 使用 easeOutQuart 缓动函数
    const easeProgress = 1 - Math.pow(1 - progress, 4);
    const current = startValue + (target - startValue) * easeProgress;
    
    element.textContent = formatNumber(current, 2) + suffix;
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

// 百分比滚动动画
function animatePercent(element, targetValue, duration = 1000) {
  if (!element) return;
  
  const target = Number(targetValue);
  if (!Number.isFinite(target)) {
    element.textContent = '-';
    return;
  }
  
  const startTime = performance.now();
  
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 4);
    const current = target * easeProgress;
    
    element.textContent = formatPct(current);
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

// 卡片进入动画（带延迟）
function animateCards(selector = '.card, .metric-item, .direction-item', stagger = 50) {
  const cards = $$(selector);
  cards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    
    setTimeout(() => {
      card.style.transition = 'all 0.3s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, index * stagger);
  });
}

// 显示/隐藏元素
function show(id) {
  const el = $(id);
  if (el) {
    el.classList.remove('hidden');
    el.style.display = '';
  }
}

function hide(id) {
  const el = $(id);
  if (el) {
    el.classList.add('hidden');
  }
}

// 设置加载状态
function setLoading(ids, loading) {
  ids.forEach(id => {
    const el = $(id);
    if (el) {
      el.disabled = loading;
      if (loading) {
        el.classList.add('is-loading');
      } else {
        el.classList.remove('is-loading');
      }
    }
  });
}

// 显示错误
function showError(message) {
  const errorBox = $('errorBox');
  if (errorBox) {
    errorBox.innerHTML = `<strong>错误</strong><div>${message}</div>`;
    errorBox.classList.remove('hidden');
    show('errorBox');
  }
}

// 清除错误
function clearError() {
  const errorBox = $('errorBox');
  if (errorBox) {
    errorBox.innerHTML = '';
    hide('errorBox');
  }
}

// 设置状态文本
function setStatus(text) {
  const statusBox = $('statusBox');
  if (statusBox) {
    statusBox.textContent = text;
  }
}

// 获取基金代码
function getFundCode() {
  const input = $('fundCode');
  return input ? input.value.trim() : '018956';
}

// 设置基金代码
function setFundCode(code) {
  const input = $('fundCode');
  if (input) input.value = code;
}

// 从URL获取基金代码
function getFundCodeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('code') || '018956';
}

// 设置URL基金代码
function setFundCodeInUrl(code) {
  const url = new URL(window.location);
  url.searchParams.set('code', code);
  window.history.replaceState({}, '', url);
}

// 导航高亮
function highlightNav(currentPage) {
  const navItems = $$('.nav-item');
  navItems.forEach(item => {
    const page = item.dataset.page;
    if (page === currentPage) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

// 判断结论逻辑
function getConclusion(pUp, modelImprovement, auc) {
  // 如果模型质量差，返回仅风险参考
  if (modelImprovement <= 0 || auc < 0.56) {
    return {
      signal: 'risk-only',
      label: '仅适合作为风险参考',
      reliability: 'low',
      explanation: '模型预测能力弱，不建议作为主要决策依据'
    };
  }
  
  // 判断方向信号
  const pDown = 1 - pUp;
  
  if (pUp >= 0.60) {
    return {
      signal: 'bullish',
      label: '偏多',
      reliability: pUp >= 0.70 ? 'high' : 'medium',
      explanation: `上涨概率 ${formatPct(pUp)}，模型表现良好`
    };
  }
  
  if (pDown >= 0.60) {
    return {
      signal: 'bearish',
      label: '偏空',
      reliability: pDown >= 0.70 ? 'high' : 'medium',
      explanation: `下跌概率 ${formatPct(pDown)}，模型表现良好`
    };
  }
  
  return {
    signal: 'neutral',
    label: '中性',
    reliability: 'medium',
    explanation: '方向信号不明确，建议观望'
  };
}

// 导出公共函数
window.$ = $;
window.$$ = $$;
window.formatNumber = formatNumber;
window.formatPct = formatPct;
window.formatSignedPctCN = formatSignedPctCN;
window.getReturnClass = getReturnClass;
window.animateNumber = animateNumber;
window.animatePercent = animatePercent;
window.animateCards = animateCards;
window.show = show;
window.hide = hide;
window.setLoading = setLoading;
window.showError = showError;
window.clearError = clearError;
window.setStatus = setStatus;
window.getFundCode = getFundCode;
window.setFundCode = setFundCode;
window.getFundCodeFromUrl = getFundCodeFromUrl;
window.setFundCodeInUrl = setFundCodeInUrl;
window.highlightNav = highlightNav;
window.getConclusion = getConclusion;
