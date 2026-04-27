/**
 * 模型训练与诊断页面
 */

function initModel() {
  highlightNav('model');
  
  const code = getFundCodeFromUrl();
  setFundCode(code);
  
  $('trainBtn')?.addEventListener('click', startModelTraining);
  $('loadBtn')?.addEventListener('click', loadModelDiagnostics);
  
  if (code) {
    loadModelDiagnostics();
  }
}

async function loadModelDiagnostics() {
  const code = getFundCode();
  if (!code) return;
  
  setFundCodeInUrl(code);
  setBusy(['loadBtn'], true);
  
  try {
    const modelRes = await fetchModelInfo(code);
    renderModelDiagnostics(modelRes);
  } catch (err) {
    showError('加载失败: ' + err.message);
    // 显示空状态
    show('emptyState');
    hide('modelContent');
  } finally {
    setBusy(['loadBtn'], false);
  }
}

function renderModelDiagnostics(data) {
  if (!data) {
    show('emptyState');
    hide('modelContent');
    return;
  }
  
  hide('emptyState');
  show('modelContent');
  
  const metrics = data.metrics || {};
  const config = data.config || {};
  
  // 模型文件状态
  const modelExists = data.point_model_exists || false;
  $('modelFileStatus').textContent = modelExists ? '已存在' : '未训练';
  $('modelFileStatus').className = `status-badge ${modelExists ? 'exists' : 'missing'}`;
  
  // 训练模式配置
  $('trainingMode').textContent = metrics.training_mode || 'fast';
  $('refineTopK').textContent = metrics.refine_top_k || '-';
  $('walkForwardStep').textContent = metrics.walk_forward_step || '-';
  $('maxWalkForwardPoints').textContent = metrics.max_walk_forward_points || '无限制';
  $('walkForwardEvalPoints').textContent = metrics.walk_forward_eval_points || '-';
  
  // 特征数量
  const pointFeatures = config.selected_features_point || [];
  const directionFeatures = config.selected_features_direction || [];
  $('pointFeatureCount').textContent = pointFeatures.length;
  $('directionFeatureCount').textContent = directionFeatures.length;
  
  // 泄露检查
  const hasLeakage = checkLeakage(pointFeatures, directionFeatures);
  $('leakageStatus').textContent = hasLeakage ? '❌ 发现泄露列' : '✅ 通过';
  $('leakageStatus').className = hasLeakage ? 'status-error' : 'status-ok';
  
  // 泄露列列表
  if (hasLeakage) {
    const leakageCols = findLeakageCols(pointFeatures, directionFeatures);
    $('leakageCols').textContent = leakageCols.join(', ');
    show('leakageDetail');
  } else {
    hide('leakageDetail');
  }
  
  // 核心指标
  const point = metrics.point || {};
  const direction = metrics.direction || {};
  
  $('modelVsMeanImprovement').textContent = point.model_vs_mean_improvement !== undefined ? 
    (point.model_vs_mean_improvement * 100).toFixed(1) + '%' : '-';
  $('predRealCorr').textContent = point.pred_real_corr !== undefined ? point.pred_real_corr.toFixed(3) : '-';
  $('predRealStdRatio').textContent = point.pred_real_std_ratio !== undefined ? point.pred_real_std_ratio.toFixed(3) : '-';
  $('auc').textContent = direction.auc !== undefined ? direction.auc.toFixed(3) : '-';
  $('brier').textContent = direction.brier_score !== undefined ? direction.brier_score.toFixed(3) : '-';
  
  // 特征列表
  renderFeatureList('pointFeatureList', pointFeatures);
  renderFeatureList('directionFeatureList', directionFeatures);
}

function checkLeakage(pointFeatures, directionFeatures) {
  const allFeatures = [...(pointFeatures || []), ...(directionFeatures || [])];
  const leakageKeywords = ['target', 'next', 'future', 'label'];
  
  return allFeatures.some(f => {
    const fl = f.toLowerCase();
    return leakageKeywords.some(kw => fl.includes(kw));
  });
}

function findLeakageCols(pointFeatures, directionFeatures) {
  const allFeatures = [...(pointFeatures || []), ...(directionFeatures || [])];
  const leakageKeywords = ['target', 'next', 'future', 'label'];
  
  return allFeatures.filter(f => {
    const fl = f.toLowerCase();
    return leakageKeywords.some(kw => fl.includes(kw));
  });
}

function renderFeatureList(elementId, features) {
  const container = $(elementId);
  if (!container) return;
  
  if (!features || features.length === 0) {
    container.innerHTML = '<div class="empty-text">暂无特征数据</div>';
    return;
  }
  
  container.innerHTML = features.map((f, i) => `
    <div class="feature-item">
      <span class="feature-index">${i + 1}</span>
      <span class="feature-name">${f}</span>
    </div>
  `).join('');
}

async function startModelTraining() {
  const code = getFundCode();
  if (!code) {
    showError('请输入基金代码');
    return;
  }
  
  clearError();
  setBusy(['trainBtn'], true);
  setStatus('开始训练...');
  
  try {
    const trainRes = await startTraining(code, true);
    const taskId = trainRes.task_id;
    
    // 显示进度区域
    show('progressWrap');
    
    // 轮询任务状态
    await pollTrainingTask(taskId);
    
    // 训练完成后加载诊断
    setStatus('训练完成，加载诊断...');
    await loadModelDiagnostics();
    setStatus('训练完成');
  } catch (err) {
    showError(err.message);
    setStatus('训练失败');
  } finally {
    setBusy(['trainBtn'], false);
  }
}

async function pollTrainingTask(taskId) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const task = await fetchTaskStatus(taskId);
        
        // 更新进度
        if (task.progress !== undefined) {
          updateProgress(task.progress, task.stage, task.message);
        }
        
        if (task.status === 'success' || task.status === 'completed') {
          clearInterval(interval);
          updateProgress(100, 'completed', '训练完成');
          resolve(task);
        } else if (task.status === 'failed') {
          clearInterval(interval);
          reject(new Error(task.message || '训练失败'));
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, 2000);
  });
}

function updateProgress(progress, stage, message) {
  const bar = $('progressBar');
  const text = $('progressText');
  const stageEl = $('progressStage');
  
  if (bar) bar.style.width = progress + '%';
  if (text) text.textContent = progress + '%';
  if (stageEl) stageEl.textContent = message || stage || '';
}

document.addEventListener('DOMContentLoaded', initModel);
