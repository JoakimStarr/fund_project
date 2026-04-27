/**
 * 总览 / T+1 风险预测页面
 */

let currentChart = null;

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
  setBusy(['predictBtn', 'trainBtn'], true);
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
    setBusy(['predictBtn', 'trainBtn'], false);
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
  setBusy(['predictBtn', 'trainBtn'], true);
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
    setBusy(['predictBtn', 'trainBtn'], false);
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

// 渲染总览页面
function renderDashboard(data) {
  if (!data) return;
  
  // 隐藏空状态
  hide('emptyState');
  show('dashboardContent');
  
  // 基本信息
  const asofDate = data.asof_date || '-';
  const targetDate = data.prediction?.target_date || '-';
  $('asofDate').textContent = asofDate;
  $('targetDate').textContent = targetDate;
  
  // 主结论
  const conclusion = data.conclusion || {};
  const reliability = conclusion.reliability || 'unknown';
  const reliabilityText = {
    'high': '高可信',
    'medium': '中等可信',
    'low': '低可信',
    'unknown': '未知'
  }[reliability] || '未知';
  
  $('reliabilityBadge').className = `reliability-badge ${reliability}`;
  $('reliabilityBadge').textContent = reliabilityText;
  
  // 方向信号
  const direction = data.direction || {};
  const signal = direction.signal || 'neutral';
  const signalText = {
    'bullish': '看涨',
    'bearish': '看跌',
    'neutral': '中性'
  }[signal] || '中性';
  
  $('directionSignal').textContent = signalText;
  $('directionSignal').className = `direction-signal ${signal}`;
  $('pUpValue').textContent = formatPct(direction.p_up);
  
  // 点预测
  const point = data.point || {};
  $('pointReturn').textContent = formatSignedPctCN(point.pred_return);
  $('pointReturn').className = `point-return ${getReturnClass(point.pred_return)}`;
  
  // 80%区间
  const interval80 = data.interval_80 || {};
  $('interval80Lower').textContent = formatSignedPctCN(interval80.lower);
  $('interval80Upper').textContent = formatSignedPctCN(interval80.upper);
  
  // 净值区间
  const currentNav = data.current_nav;
  if (currentNav && interval80.lower !== undefined) {
    const navLower = currentNav * (1 + interval80.lower);
    const navUpper = currentNav * (1 + interval80.upper);
    $('navInterval').textContent = `${formatNav(navLower)} ~ ${formatNav(navUpper)}`;
  }
  
  // Proxy R2
  const proxyR2 = data.proxy_r2_60;
  $('proxyR2').textContent = proxyR2 !== undefined ? proxyR2.toFixed(3) : '-';
  
  // 解释力等级
  const explanatoryPower = data.explanatory_power || 'unknown';
  const expText = {
    'high': '强',
    'medium': '中等',
    'low': '弱',
    'unknown': '未知'
  }[explanatoryPower] || '未知';
  $('explanatoryPower').textContent = expText;
  
  // 最近真实预测次数
  const recentRealCount = data.recent_real_prediction_count || 0;
  $('recentRealCount').textContent = recentRealCount;
}

// 初始化
document.addEventListener('DOMContentLoaded', initDashboard);
