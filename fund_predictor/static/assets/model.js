/**
 * Quant Dashboard - 模型系统页面逻辑
 */

function initModel() {
  highlightNav('model');
  const code = getFundCodeFromUrl();
  setFundCode(code);
  $('loadBtn')?.addEventListener('click', loadModelData);
  $('trainBtn')?.addEventListener('click', startTrainingTask);
  if (code) loadModelData();
}

async function loadModelData() {
  const code = getFundCode();
  if (!code) return;
  setFundCodeInUrl(code);
  setLoading(['loadBtn'], true);
  try {
    const res = await fetchModelInfo(code);
    renderModel(res);
  } catch (err) {
    showError(err.message);
    show('emptyState');
    hide('resultSection');
  } finally {
    setLoading(['loadBtn'], false);
  }
}

function renderModel(data) {
  if (!data) {
    show('emptyState');
    hide('resultSection');
    return;
  }
  hide('emptyState');
  show('resultSection');

  const metrics = data.metrics || {};
  const config = data.config || {};

  $('trainingMode').textContent = metrics.training_mode || 'fast';
  $('refineTopK').textContent = metrics.refine_top_k || '-';
  $('walkForwardStep').textContent = metrics.walk_forward_step || '-';

  const pointFeatures = config.selected_features_point || [];
  const directionFeatures = config.selected_features_direction || [];
  $('pointFeatureCount').textContent = pointFeatures.length;
  $('directionFeatureCount').textContent = directionFeatures.length;

  // 泄露检查
  const allFeatures = [...pointFeatures, ...directionFeatures];
  const hasLeakage = allFeatures.some(f => {
    const fl = f.toLowerCase();
    return ['target', 'next', 'future', 'label'].some(kw => fl.includes(kw));
  });
  $('leakageStatus').textContent = hasLeakage ? '❌ 发现泄露' : '✅ 通过';
  $('leakageStatus').className = `metric-number ${hasLeakage ? 'bad' : 'good'}`;

  // 核心指标
  const point = metrics.point || {};
  const direction = metrics.direction || {};

  $('modelVsMeanImprovement').textContent = point.model_vs_mean_improvement !== undefined ?
    (point.model_vs_mean_improvement * 100).toFixed(1) + '%' : '-';
  $('predRealCorr').textContent = point.pred_real_corr !== undefined ? point.pred_real_corr.toFixed(3) : '-';
  $('auc').textContent = direction.auc !== undefined ? direction.auc.toFixed(3) : '-';
  $('brier').textContent = direction.brier_score !== undefined ? direction.brier_score.toFixed(3) : '-';

  animateCards('.metric-item', 80);
}

async function startTrainingTask() {
  const code = getFundCode();
  if (!code) {
    showError('请输入基金代码');
    return;
  }
  clearError();
  setLoading(['trainBtn', 'loadBtn'], true);
  setStatus('开始训练...');
  show('progressWrap');

  try {
    const trainRes = await startTraining(code, true);
    const taskId = trainRes.task_id;

    await pollTrainingTask(taskId);

    setStatus('训练完成，加载诊断...');
    await loadModelData();
    setStatus('训练完成');
  } catch (err) {
    showError(err.message);
    setStatus('训练失败');
  } finally {
    setLoading(['trainBtn', 'loadBtn'], false);
    hide('progressWrap');
  }
}

async function pollTrainingTask(taskId) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const task = await fetchTaskStatus(taskId);

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
