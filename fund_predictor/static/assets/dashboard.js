/**
 * Quant Dashboard - 决策中心页面逻辑
 */

// 初始化页面
function initDashboard() {
  highlightNav('dashboard');
  
  // 从URL获取基金代码
  const code = getFundCodeFromUrl();
  setFundCode(code);
  
  // 绑定事件
  $('predictBtn')?.addEventListener('click', handlePredict);
  $('trainBtn')?.addEventListener('click', handleTrainAndPredict);
  $('fundCode')?.addEventListener('change', () => {
    setFundCodeInUrl(getFundCode());
  });
  
  // 页面加载时自动预测
  if (code) {
    handlePredict();
  }
}

// 处理预测
async function handlePredict() {
  const code = getFundCode();
  if (!code) {
    showError('请输入基金代码');
    return;
  }
  
  clearError();
  setLoading(['predictBtn', 'trainBtn'], true);
  setStatus('正在加载预测...');
  
  try {
    const forceRetrain = $('forceRetrain')?.checked || false;
    const res = await fetchPrediction(code, forceRetrain);
    renderDashboard(res.data);
    setStatus('预测完成');
  } catch (err) {
    showError(err.message);
    setStatus('预测失败');
  } finally {
    setLoading(['predictBtn', 'trainBtn'], false);
  }
}

// 处理训练并预测
async function handleTrainAndPredict() {
  const code = getFundCode();
  if (!code) {
    showError('请输入基金代码');
    return;
  }
  
  clearError();
  setLoading(['predictBtn', 'trainBtn'], true);
  setStatus('开始训练...');
  
  try {
    // 开始训练
    const trainRes = await startTraining(code, true);
    const taskId = trainRes.task_id;
    
    // 轮询任务状态
    await pollTrainingTask(taskId);
    
    // 训练完成后预测
    setStatus('训练完成，正在预测...');
    const predRes = await fetchPrediction(code, false);
    renderDashboard(predRes.data);
    setStatus('训练并预测完成');
  } catch (err) {
    showError(err.message);
    setStatus('训练失败');
  } finally {
    setLoading(['predictBtn', 'trainBtn'], false);
  }
}

// 轮询训练任务
async function pollTrainingTask(taskId) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const task = await fetchTaskStatus(taskId);
        
        if (task.status === 'success' || task.status === 'completed') {
          clearInterval(interval);
          resolve(task);
        } else if (task.status === 'failed') {
          clearInterval(interval);
          reject(new Error(task.message || '训练失败'));
        } else {
          setStatus(`训练中: ${task.message || '...'}`);
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, 2000);
  });
}

// 渲染决策中心
function renderDashboard(data) {
  if (!data) return;
  
  // 隐藏空状态，显示结果
  hide('emptyState');
  show('resultSection');
  
  // 提取关键数据
  const point = data.point || {};
  const direction = data.direction || {};
  const metrics = data.metrics || {};
  const interval80 = data.interval_80 || {};
  const interval90 = data.interval_90 || {};
  
  const pUp = direction.p_up || 0.5;
  const pDown = 1 - pUp;
  const modelImprovement = metrics.model_vs_mean_improvement || 0;
  const auc = metrics.auc || 0.5;
  
  // 获取结论
  const conclusion = getConclusion(pUp, modelImprovement, auc);
  
  // 渲染主结论
  renderConclusion(conclusion);
  
  // 渲染方向信号（带数字滚动动画）
  renderDirectionSignals(pUp, pDown);
  
  // 渲染区间
  renderIntervals(interval80, interval90);
  
  // 渲染辅助点预测
  renderPointPrediction(point.pred_return);
  
  // 渲染可信度指标
  renderMetrics(metrics);
  
  // 触发卡片动画
  setTimeout(() => {
    animateCards('.direction-item, .metric-item, .interval-card', 80);
  }, 100);
}

// 渲染主结论
function renderConclusion(conclusion) {
  const valueEl = $('conclusionValue');
  const subtitleEl = $('conclusionSubtitle');
  const badgeEl = $('reliabilityBadge');
  
  // 设置结论值和样式
  valueEl.textContent = conclusion.label;
  valueEl.className = `conclusion-value ${conclusion.signal}`;
  
  // 设置解释
  subtitleEl.textContent = conclusion.explanation;
  
  // 设置可信等级徽章
  const reliabilityText = {
    'high': '高可信',
    'medium': '中等可信',
    'low': '低可信'
  }[conclusion.reliability] || '未知';
  
  badgeEl.textContent = reliabilityText;
  badgeEl.className = `reliability-badge ${conclusion.reliability}`;
}

// 渲染方向信号
function renderDirectionSignals(pUp, pDown) {
  const upEl = $('upProbability');
  const downEl = $('downProbability');
  const neutralEl = $('neutralRange');
  
  // 数字滚动动画
  animatePercent(upEl, pUp, 800);
  animatePercent(downEl, pDown, 800);
  
  // 中性区间
  const neutralMin = Math.min(pUp, pDown);
  const neutralMax = Math.max(pUp, pDown);
  neutralEl.textContent = `${(neutralMin * 100).toFixed(0)}-${(neutralMax * 100).toFixed(0)}%`;
  
  // 高亮活跃项
  const upItem = $('upItem');
  const downItem = $('downItem');
  const neutralItem = $('neutralItem');
  
  upItem.classList.remove('active');
  downItem.classList.remove('active');
  neutralItem.classList.remove('active');
  
  if (pUp >= 0.60) {
    upItem.classList.add('active');
  } else if (pDown >= 0.60) {
    downItem.classList.add('active');
  } else {
    neutralItem.classList.add('active');
  }
}

// 渲染区间
function renderIntervals(interval80, interval90) {
  // 80%区间
  const lower80 = interval80.lower || -0.02;
  const upper80 = interval80.upper || 0.02;
  
  $('interval80Lower').textContent = formatSignedPctCN(lower80);
  $('interval80Upper').textContent = formatSignedPctCN(upper80);
  
  // 更新区间条位置和宽度
  const range80 = upper80 - lower80;
  const center80 = (upper80 + lower80) / 2;
  const bar80 = $('interval80Range');
  const centerLine80 = $('interval80Center');
  
  // 将数值映射到百分比位置（假设范围 -10% 到 +10%）
  const minVal = -0.10;
  const maxVal = 0.10;
  const totalRange = maxVal - minVal;
  
  const leftPercent = ((lower80 - minVal) / totalRange) * 100;
  const widthPercent = (range80 / totalRange) * 100;
  const centerPercent = ((center80 - minVal) / totalRange) * 100;
  
  bar80.style.left = `${Math.max(0, leftPercent)}%`;
  bar80.style.width = `${Math.min(100, widthPercent)}%`;
  centerLine80.style.left = `${Math.max(0, Math.min(100, centerPercent))}%`;
  
  // 90%区间
  const lower90 = interval90.lower || -0.03;
  const upper90 = interval90.upper || 0.03;
  
  $('interval90Lower').textContent = formatSignedPctCN(lower90);
  $('interval90Upper').textContent = formatSignedPctCN(upper90);
  
  const range90 = upper90 - lower90;
  const center90 = (upper90 + lower90) / 2;
  const bar90 = $('interval90Range');
  const centerLine90 = $('interval90Center');
  
  const leftPercent90 = ((lower90 - minVal) / totalRange) * 100;
  const widthPercent90 = (range90 / totalRange) * 100;
  const centerPercent90 = ((center90 - minVal) / totalRange) * 100;
  
  bar90.style.left = `${Math.max(0, leftPercent90)}%`;
  bar90.style.width = `${Math.min(100, widthPercent90)}%`;
  centerLine90.style.left = `${Math.max(0, Math.min(100, centerPercent90))}%`;
}

// 渲染辅助点预测
function renderPointPrediction(predReturn) {
  const el = $('pointPrediction');
  if (predReturn !== undefined && predReturn !== null) {
    el.textContent = formatSignedPctCN(predReturn);
    el.className = `auxiliary-value ${getReturnClass(predReturn)}`;
  } else {
    el.textContent = '-';
  }
}

// 渲染可信度指标
function renderMetrics(metrics) {
  const improvement = metrics.model_vs_mean_improvement || 0;
  const corr = metrics.pred_real_corr || 0;
  const auc = metrics.auc || 0;
  const proxyR2 = metrics.proxy_r2_60 || 0;
  
  // 模型改进度
  const impEl = $('metricImprovement');
  impEl.textContent = formatPct(improvement);
  impEl.className = `metric-number ${improvement > 0 ? 'good' : 'bad'}`;
  
  // 预测-真实相关
  const corrEl = $('metricCorr');
  corrEl.textContent = corr.toFixed(3);
  corrEl.className = `metric-number ${corr > 0.3 ? 'good' : corr > 0.1 ? '' : 'bad'}`;
  
  // AUC
  const aucEl = $('metricAuc');
  aucEl.textContent = auc.toFixed(3);
  aucEl.className = `metric-number ${auc > 0.6 ? 'good' : auc > 0.55 ? '' : 'bad'}`;
  
  // Proxy R²
  const r2El = $('metricProxyR2');
  r2El.textContent = proxyR2.toFixed(3);
  r2El.className = `metric-number ${proxyR2 > 0.5 ? 'good' : proxyR2 > 0.3 ? '' : 'bad'}`;
}

// 初始化
document.addEventListener('DOMContentLoaded', initDashboard);
