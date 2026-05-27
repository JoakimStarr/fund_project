const $ = (id) => document.getElementById(id);

let currentChart = null;
let lastBacktestRows = [];

function fundCode() {
  return ($("fundCode")?.value || "018956").trim();
}

function num(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function formatPct(x, digits = 2) {
  const n = num(x);
  return n === null ? "-" : `${(n * 100).toFixed(digits)}%`;
}

function formatBp(x, digits = 1) {
  const n = num(x);
  return n === null ? "-" : `${n.toFixed(digits)} bp`;
}

function formatNav(x, digits = 4) {
  const n = num(x);
  return n === null ? "-" : n.toFixed(digits);
}

function formatSignedPctCN(x, digits = 2) {
  const n = num(x);
  if (n === null) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(digits)}%`;
}

function getCnReturnClass(x) {
  const n = num(x);
  if (n === null || n === 0) return "neutral";
  return n > 0 ? "positive-cn" : "negative-cn";
}

function renderBadge(label, type = "neutral") {
  return `<span class="badge badge-${type}">${label}</span>`;
}

function renderMetricCard(label, value, subtext = "", status = "neutral") {
  return `
    <article class="metric-card ${status}">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
      ${subtext ? `<div class="metric-subtext">${subtext}</div>` : ""}
    </article>
  `;
}

function renderPriorityCard(label, value, subtext = "", status = "neutral") {
  return `
    <article class="priority-card ${status}">
      <div class="metric-label">${label}</div>
      <div class="priority-value">${value}</div>
      ${subtext ? `<div class="metric-subtext">${subtext}</div>` : ""}
    </article>
  `;
}

function renderInterval(label, lower, upper, cls = "") {
  return `
    <div class="interval ${cls}">
      <span>${label}</span>
      <strong>${formatSignedPctCN(lower)} ~ ${formatSignedPctCN(upper)}</strong>
    </div>
  `;
}

function setBusy(busy) {
  ["predictBtn", "trainBtn"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.disabled = busy;
    el.classList.toggle("is-loading", busy);
  });
}

function setStatus(text) {
  if ($("statusBox")) $("statusBox").textContent = text;
}

function setProgress(progress, stage, message, status = "running") {
  const wrap = $("progressWrap");
  const bar = $("progressBar");
  const text = $("progressText");
  const stageEl = $("progressStage");
  if (!wrap || !bar || !text || !stageEl) return;

  wrap.classList.toggle("idle", status === "idle");
  wrap.classList.toggle("completed", status === "success" || status === "completed");

  if (status === "success" || status === "completed") {
    bar.style.width = "100%";
    text.textContent = "100%";
    stageEl.textContent = "训练完成";
    return;
  }
  if (status === "idle") {
    bar.style.width = "0%";
    text.textContent = "";
    stageEl.textContent = "暂无训练任务";
    return;
  }
  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
  bar.style.width = `${safeProgress}%`;
  text.textContent = `${safeProgress}%`;
  stageEl.innerHTML = `<span class="loading-spinner"></span>${stage || "训练进度"}${message ? ` · ${message}` : ""}`;
}

function detailLines(details = {}) {
  const keys = [
    "nav_rows", "nav_start_date", "nav_end_date", "nav_source", "source_used",
    "fallback_used", "fallback_reason", "min_required_rows", "suspected_reason",
    "proxy_unavailable_reason", "failed_stock_codes", "failed_themes",
  ];
  return keys
    .filter((key) => details[key] !== undefined && details[key] !== null && details[key] !== "")
    .map((key) => `<div><b>${key}</b>: ${Array.isArray(details[key]) ? details[key].join(", ") : details[key]}</div>`)
    .join("");
}

function renderErrorCard(error) {
  return `
    <div class="error-title">${error.code || "UNKNOWN"}</div>
    <div class="error-grid">
      <div><span>stage</span><b>${error.stage || "-"}</b></div>
      <div><span>request_id</span><b>${error.request_id || "-"}</b></div>
      <div><span>task_id</span><b>${error.task_id || "-"}</b></div>
    </div>
    <p>${error.message || "未知错误"}</p>
    <div class="error-details">${detailLines(error.details || {})}</div>
    <p class="subtle-text">建议查看 logs/error.log 获取 traceback。</p>
  `;
}

function showError(err) {
  const box = $("errorBox");
  if (!box) return;
  box.innerHTML = renderErrorCard(err || {});
  box.classList.remove("hidden");
  if ($("latestRequestId") && err?.request_id) $("latestRequestId").textContent = err.request_id;
}

function clearError() {
  $("errorBox")?.classList.add("hidden");
}

async function api(url, options = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await res.json();
  if (!data.ok) throw data.error;
  return data;
}

function signalText(signal) {
  return { bullish: "偏多", bearish: "偏空", neutral: "中性", unavailable: "不可用" }[signal] || signal || "-";
}

function strengthText(strength) {
  return { strong: "强", weak: "弱", none: "无" }[strength] || strength || "-";
}

function qualityBadge(flag) {
  if (flag === "high") return renderBadge("高", "success");
  if (flag === "medium") return renderBadge("中", "warning");
  if (flag === "low") return renderBadge("低", "neutral");
  return renderBadge(flag || "不可用", "neutral");
}

function shouldRiskOnly(data) {
  const m = data.metrics || {};
  const point = m.point || {};
  const direction = m.direction || {};
  return (
    num(point.model_vs_mean_improvement) <= 0 &&
    num(point.pred_real_std_ratio) !== null &&
    num(point.pred_real_std_ratio) < 0.15 &&
    (num(direction.auc) === null || num(direction.auc) < 0.56)
  );
}

function pointUsability(data) {
  const point = (data.metrics || {}).point || {};
  const health = data.point_prediction_health || {};
  const improvement = num(point.model_vs_mean_improvement ?? health.model_vs_mean_improvement);
  if (health.flat_prediction || health.near_baseline || improvement === null || improvement <= 0) return "unusable";
  if (improvement < 0.05) return "weak";
  return "usable";
}

function directionExplanation(data) {
  if (data.direction_signal === "bullish") return "上涨概率达到有效偏多阈值，但仍需结合区间风险。";
  if (data.direction_signal === "bearish") return "下跌概率达到有效偏空阈值，但仍需结合区间风险。";
  if (data.p_up != null && data.p_down != null) {
    if (data.p_down > data.p_up) return "下跌概率略高，但未达到有效偏空阈值，因此方向信号为中性。";
    if (data.p_up > data.p_down) return "上涨概率略高，但未达到有效偏多阈值，因此方向信号为中性。";
  }
  return "方向概率未达到有效阈值，因此方向信号为中性。";
}

function renderUsabilityCard(data) {
  const metrics = data.metrics || {};
  const point = metrics.point || {};
  const direction = metrics.direction || {};
  const proxyR2 = num(data.proxy_r2_60);
  const usable = pointUsability(data);
  const isBullish = data.direction_signal === "bullish";
  const isBearish = data.direction_signal === "bearish";
  const badge = isBullish ? renderBadge("偏多信号", "danger") : isBearish ? renderBadge("偏空信号", "success") : renderBadge("无有效方向信号", "neutral");
  const title = isBullish ? "偏多信号" : isBearish ? "偏空信号" : "无有效方向信号";
  const pointText = usable !== "usable"
    ? `点预测收益率为 ${formatSignedPctCN(data.pred_return ?? data.pred)}，但点预测未显著优于均值基准，仅作辅助，不作为涨跌方向判断。`
    : `点预测收益率为 ${formatSignedPctCN(data.pred_return ?? data.pred)}，仍只作为方向模型之外的辅助信息。`;
  const text = `${directionExplanation(data)} ${pointText}`;
  const stripClass = isBullish ? "bullish" : isBearish ? "bearish" : "neutral";

  $("usabilityCard").classList.remove("muted-card");
  $("usabilityCard").innerHTML = `
    <div class="risk-strip ${stripClass}"></div>
    <div>
      ${badge}
      <h2>${title}</h2>
      <p>${text}</p>
      <div class="evidence-row">
        <span>均值基准提升 <b>${formatPct(point.model_vs_mean_improvement, 2)}</b></span>
        <span>AUC <b>${num(direction.auc) === null ? "-" : num(direction.auc).toFixed(3)}</b></span>
        <span>proxy_r2_60 <b>${proxyR2 === null ? "-" : proxyR2.toFixed(3)}</b></span>
      </div>
    </div>
  `;
}

function renderCoreMetrics(data) {
  const intervals = data.intervals || {};
  const i80 = intervals["80"] || {};
  const i90 = intervals["90"] || {};
  const nav80 = data.nav_interval_80 || {};
  const nav90 = data.nav_interval_90 || {};
  const pred = num(data.pred_return ?? data.pred);
  const usable = pointUsability(data);
  const pointWeak = usable !== "usable";
  const pointNote = pointWeak ? "该数值来自回归模型，但点预测当前不可用，不代表有效上涨判断。" : "该数值来自 point_model，仅作辅助。";
  const navNote = pointWeak ? "由辅助点预测换算，可信度较低。" : "由 point_model 收益率换算。";
  const directionTitle = data.direction_signal === "bullish" ? "偏多信号" : data.direction_signal === "bearish" ? "偏空信号" : "无有效方向信号";
  const directionClass = data.direction_signal === "bullish" ? "bullish" : data.direction_signal === "bearish" ? "bearish" : "neutral";
  const priority = $("priorityMetrics");
  if (priority) {
    priority.innerHTML = [
      renderPriorityCard("方向结论", directionTitle, directionExplanation(data), directionClass),
      renderPriorityCard("80% 主参考区间", renderInterval("", i80.lower, i80.upper), "收益率区间，优先参考", "primary"),
      renderPriorityCard("90% 风险区间", renderInterval("", i90.lower, i90.upper), "收益率区间，用于风险边界", "warning"),
      renderPriorityCard("80% / 90% 净值区间", `${formatNav(nav80.lower)} ~ ${formatNav(nav80.upper)}<small>80%</small><br>${formatNav(nav90.lower)} ~ ${formatNav(nav90.upper)}<small>90%</small>`, "净值口径风险范围", "neutral"),
    ].join("");
  }
  $("coreMetrics").innerHTML = [
    renderMetricCard("今日净值", formatNav(data.today_nav), `截至 ${data.asof_date || "-"}`, "neutral"),
    renderMetricCard("点预测明日净值（辅助）", formatNav(data.pred_nav), navNote, pointWeak ? "muted-card" : "primary"),
    renderMetricCard("点预测收益率（辅助）", formatSignedPctCN(pred), pointNote, pointWeak ? "muted-card" : getCnReturnClass(pred)),
    renderMetricCard("上涨概率", data.p_up == null ? "不可用" : formatPct(data.p_up, 2), signalText(data.direction_signal), "positive-cn"),
    renderMetricCard("下跌概率", data.p_down == null ? "不可用" : formatPct(data.p_down, 2), strengthText(data.direction_strength), "negative-cn"),
  ].join("");

  const i99 = intervals["99"] || {};
  const nav99 = data.nav_interval_99 || {};
  $("interval99").innerHTML = `
    ${renderInterval("99% 收益率极端风险区间", i99.lower, i99.upper)}
    <div class="interval"><span>99% 净值极端风险区间</span><strong>${formatNav(nav99.lower)} ~ ${formatNav(nav99.upper)}</strong></div>
  `;
}

function renderDirectionCard(data) {
  const direction = (data.metrics || {}).direction || {};
  const dh = data.direction_health || {};
  const strongCount = num(dh.strong_signal_count ?? direction.strong_signal_count) || 0;
  const strongRate = dh.strong_signal_win_rate ?? direction.strong_signal_win_rate;
  const strongText = strongCount < 20
    ? "强信号样本数不足，历史胜率暂不具备统计参考价值。"
    : `强信号历史胜率 ${formatPct(strongRate, 2)}`;
  const directionMsg = data.direction_signal === "neutral"
    ? directionExplanation(data)
    : data.p_up >= 0.6
      ? "偏多信号，但仍需结合区间风险。"
      : data.p_down >= 0.6
        ? "偏空信号，但仍需结合区间风险。"
        : "方向信号较弱。";

  $("directionCard").innerHTML = `
    <div class="section-title">方向信号</div>
    <div class="split-metrics">
      <div><span>上涨概率</span><b class="positive-cn">${data.p_up == null ? "不可用" : formatPct(data.p_up, 2)}</b></div>
      <div><span>下跌概率</span><b class="negative-cn">${data.p_down == null ? "不可用" : formatPct(data.p_down, 2)}</b></div>
      <div><span>方向信号</span><b>${signalText(data.direction_signal)}</b></div>
      <div><span>方向强度</span><b>${strengthText(data.direction_strength)}</b></div>
      <div><span>强信号样本数</span><b>${strongCount}</b></div>
      <div><span>AUC</span><b>${num(direction.auc) === null ? "-" : num(direction.auc).toFixed(3)}</b></div>
      <div><span>概率列</span><b>up=${data.p_up_source_class ?? "-"} / down=${data.p_down_source_class ?? "-"}</b></div>
    </div>
    <div class="notice ${strongCount < 20 ? "warning" : ""}">${strongText}</div>
    <p class="subtle-text">${dh.message || directionMsg}</p>
  `;
}

function renderProxyCard(data) {
  const available = data.proxy_available !== false;
  const reason = data.proxy_unavailable_reason || "代理组合暂不可用，当前结果基于历史收益和市场因子。";
  const helpful = data.proxy_features_helpful === true ? renderBadge("有提升", "success") : renderBadge("未证实提升", "neutral");
  const top10Status = data.top10_proxy_status || "unavailable";
  const failedCodes = data.failed_stock_codes || [];
  const sourcesUsed = data.stock_sources_used || {};
  const topExposures = data.top_exposures || [];
  const top10Unavailable = top10Status === "unavailable";
  const top10Partial = top10Status === "partial";

  let top10StatusBadge = renderBadge(top10Status, top10Status === "usable" ? "success" : top10Status === "partial" ? "warning" : "danger");
  let top10Warning = "";
  if (top10Unavailable) {
    top10Warning = `<div class="notice warning">重仓股代理不可用，当前代理组合主要依赖主题指数和收益反推。</div>`;
  } else if (top10Partial) {
    top10Warning = `<div class="notice">部分重仓股行情获取失败，代理组合可能存在偏差。</div>`;
  }

  let sourcesHtml = "";
  if (Object.keys(sourcesUsed).length > 0) {
    const sourceItems = Object.entries(sourcesUsed).map(([code, src]) => `<span>${code}: ${src}</span>`).join("");
    sourcesHtml = `<details class="source-details"><summary>数据源详情 (${Object.keys(sourcesUsed).length}只)</summary><div class="source-grid">${sourceItems}</div></details>`;
  }

  let failedHtml = "";
  if (failedCodes.length > 0) {
    failedHtml = `<details class="failed-details"><summary>失败股票 (${failedCodes.length}只)</summary><div class="failed-codes">${failedCodes.join(", ")}</div></details>`;
  }

  let exposuresHtml = "";
  if (topExposures.length > 0) {
    const exposureItems = topExposures.map(e => `<span class="exposure-item"><b>${e.name}</b>: ${e.sign === "positive" ? "+" : "-"}${(e.beta * 100).toFixed(1)}%</span>`).join("");
    exposuresHtml = `<div class="exposures-row"><span>主要暴露因子:</span>${exposureItems}</div>`;
  }

  $("proxyCard").innerHTML = `
    <div class="section-title">基金代理资产组合</div>
    ${!available ? `<div class="notice warning">${reason}</div>` : ""}
    ${top10Warning}
    <div class="split-metrics">
      <div><span>持仓报告日期</span><b>${data.holding_report_date || "-"}</b></div>
      <div><span>持仓范围</span><b>${data.holding_scope || "unavailable"}</b></div>
      <div><span>Top10 状态</span><b>${top10StatusBadge}</b></div>
      <div><span>成功股票数量</span><b>${data.top10_proxy_available_count ?? 0}</b></div>
      <div><span>缺失股票数量</span><b>${data.top10_proxy_missing_count ?? 0}</b></div>
      <div><span>主题代理成功</span><b>${data.theme_available_count ?? 0}</b></div>
      <div><span>proxy_r2_60</span><b>${num(data.proxy_r2_60) === null ? "-" : num(data.proxy_r2_60).toFixed(3)}</b></div>
      <div><span>tracking_error_60</span><b>${formatPct(data.tracking_error_60, 2)}</b></div>
      <div><span>解释力</span><b>${qualityBadge(data.proxy_quality_flag)}</b></div>
      <div><span>代理特征贡献</span><b>${helpful}</b></div>
    </div>
    ${exposuresHtml}
    ${sourcesHtml}
    ${failedHtml}
    <p class="subtle-text">代理组合基于公开披露持仓、主题指数和历史收益拟合构建，不代表基金真实实时持仓。</p>
    ${data.proxy_quality_flag === "low" ? `<div class="notice">代理组合对该基金近期收益解释力较弱，点预测可信度较低。</div>` : ""}
  `;
}

function renderExcessSignalsCard(data) {
  const signals = data.excess_signals || {};
  const cyb = signals.outperform_cyb;
  const kcb50 = signals.outperform_kcb50;
  const top10 = signals.outperform_top10;
  const theme = signals.outperform_theme;
  const stronger = signals.stronger_than_absolute;
  const reliableCount = signals.reliable_count || 0;

  let signalRows = "";
  if (cyb) {
    const badge = cyb.reliable ? renderBadge(cyb.direction === "outperform" ? "跑赢" : "跑输", cyb.direction === "outperform" ? "success" : "danger") : renderBadge("不可靠", "neutral");
    signalRows += `<div><span>vs 创业板</span><b>${badge}</b><span class="subtle-text">prob ${(cyb.prob * 100).toFixed(1)}%</span></div>`;
  }
  if (kcb50) {
    const badge = kcb50.reliable ? renderBadge(kcb50.direction === "outperform" ? "跑赢" : "跑输", kcb50.direction === "outperform" ? "success" : "danger") : renderBadge("不可靠", "neutral");
    signalRows += `<div><span>vs 科创50</span><b>${badge}</b><span class="subtle-text">prob ${(kcb50.prob * 100).toFixed(1)}%</span></div>`;
  }
  if (top10) {
    const badge = top10.reliable ? renderBadge(top10.direction === "outperform" ? "跑赢" : "跑输", top10.direction === "outperform" ? "success" : "danger") : renderBadge("不可靠", "neutral");
    signalRows += `<div><span>vs Top10代理</span><b>${badge}</b><span class="subtle-text">prob ${(top10.prob * 100).toFixed(1)}%</span></div>`;
  }
  if (theme) {
    const badge = theme.reliable ? renderBadge(theme.direction === "outperform" ? "跑赢" : "跑输", theme.direction === "outperform" ? "success" : "danger") : renderBadge("不可靠", "neutral");
    signalRows += `<div><span>vs 主题代理</span><b>${badge}</b><span class="subtle-text">prob ${(theme.prob * 100).toFixed(1)}%</span></div>`;
  }

  if (!signalRows) {
    signalRows = `<div class="notice">相对收益模型暂不可用，需要更多训练数据。</div>`;
  }

  $("excessSignalsCard").innerHTML = `
    <div class="section-title">相对收益信号</div>
    <div class="split-metrics">${signalRows}</div>
    ${stronger ? `<div class="notice success">相对收益信号强于绝对收益信号。</div>` : ""}
    ${reliableCount > 0 ? `<p class="subtle-text">可靠模型数量: ${reliableCount}</p>` : ""}
  `;
}

function renderModelMonitoringCard(data) {
  const monitoring = data.model_monitoring || {};
  const predictions = monitoring.predictions || [];
  const degradation = monitoring.degradation_flag;
  const avgImprovement = monitoring.avg_model_vs_mean_improvement;
  const directionAcc = monitoring.recent_direction_acc;

  const recentCount = predictions.length;
  const degradationBadge = degradation ? renderBadge("模型退化", "danger") : renderBadge("正常", "success");

  let recentRows = "";
  if (predictions.length > 0) {
    const recent = predictions.slice(-5);
    recentRows = recent.map(r => `
      <div class="monitoring-row">
        <span>${r.date || "-"}</span>
        <span>预测: ${formatSignedPctCN(r.pred_return)}</span>
        <span>p_up: ${formatPct(r.p_up, 1)}</span>
        <span>${r.direction_signal || "-"}</span>
      </div>
    `).join("");
  }

  $("modelMonitoringCard").innerHTML = `
    <div class="section-title">模型监控</div>
    <div class="split-metrics">
      <div><span>状态</span><b>${degradationBadge}</b></div>
      <div><span>最近预测次数</span><b>${recentCount}</b></div>
      ${avgImprovement !== undefined ? `<div><span>平均提升</span><b>${formatPct(avgImprovement, 2)}</b></div>` : ""}
      ${directionAcc !== undefined ? `<div><span>近期方向准确率</span><b>${formatPct(directionAcc, 1)}</b></div>` : ""}
    </div>
    ${degradation ? `<div class="notice warning">模型可能已退化，建议重新训练。</div>` : ""}
    ${data.exposure_shift_flag ? `<div class="notice warning">近期基金暴露可能发生漂移，点预测可信度下降。</div>` : ""}
    ${recentRows ? `<details class="monitoring-details"><summary>最近5次预测</summary>${recentRows}</details>` : ""}
  `;
}

function renderHealthCard(data) {
  const metrics = data.metrics || {};
  const point = metrics.point || {};
  const direction = metrics.direction || {};
  const interval = metrics.interval || {};
  const ph = data.point_prediction_health || {};
  const ih = data.interval_health || {};
  const improvement = num(point.model_vs_mean_improvement);
  const pointBadge = ph.flat_prediction || improvement <= 0 ? renderBadge("unusable", "danger") : improvement < 0.05 ? renderBadge("weak", "warning") : renderBadge("usable", "success");
  const directionBadge = num(direction.auc) === null || num(direction.auc) < 0.56 ? renderBadge("weak", "warning") : renderBadge("usable", "success");
  const intervalBadge = ih.status === "very_wide" ? renderBadge("very_wide", "danger") : ih.status === "wide" ? renderBadge("wide", "warning") : renderBadge("normal", "success");

  $("healthCard").innerHTML = `
    <div class="section-title">模型健康</div>
    <div class="health-grid">
      <div>${pointBadge}<h3>点预测健康</h3><p>${ph.message || "点预测仅作辅助。"}</p></div>
      <div>${directionBadge}<h3>方向概率健康</h3><p>${(data.direction_health || {}).message || "方向概率仅在强信号足够时参考。"}</p></div>
      <div>${intervalBadge}<h3>区间健康</h3><p>${ih.message || "区间用于风险参考。"}</p></div>
    </div>
    <div class="split-metrics compact">
      <div><span>是否跑赢均值基准</span><b>${formatPct(point.model_vs_mean_improvement, 2)}</b></div>
      <div><span>pred_real_corr</span><b>${num(point.pred_real_corr) === null ? "-" : num(point.pred_real_corr).toFixed(3)}</b></div>
      <div><span>pred_real_std_ratio</span><b>${num(point.pred_real_std_ratio) === null ? "-" : num(point.pred_real_std_ratio).toFixed(3)}</b></div>
      <div><span>AUC</span><b>${num(direction.auc) === null ? "-" : num(direction.auc).toFixed(3)}</b></div>
      <div><span>Brier</span><b>${num(direction.brier_score) === null ? "-" : num(direction.brier_score).toFixed(3)}</b></div>
      <div><span>Coverage 80/90</span><b>${formatPct(interval.coverage_80, 1)} / ${formatPct(interval.coverage_90, 1)}</b></div>
      <div><span>Width 80/90</span><b>${formatBp(interval.width_80_bp, 1)} / ${formatBp(interval.width_90_bp, 1)}</b></div>
    </div>
  `;
}

function renderHistoryTable(rows) {
  const wrap = $("historyWrap");
  if (!wrap) return;
  if (!rows || rows.length === 0) {
    wrap.innerHTML = `<div class="empty-state">暂无历史预测记录，请先完成一次预测。</div>`;
    return;
  }
  const latest = rows.slice(-30).reverse();
  wrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>预测时间</th><th>截至日期</th><th>预测明日净值</th><th>实际净值</th>
          <th>预测收益率</th><th>实际收益率</th><th>绝对误差 bp</th><th>p_up</th>
          <th>方向信号</th><th>强信号</th><th>方向正确</th><th>覆盖80/90</th><th>proxy_quality</th>
        </tr>
      </thead>
      <tbody>
        ${latest.map((r) => {
          const predRet = r.pred_return ?? r.pred;
          const actual = r.actual ?? r.target_next;
          return `
            <tr>
              <td>${r.created_at || r.prediction_time || "-"}</td>
              <td>${r.asof_date || r.date || "-"}</td>
              <td class="num">${formatNav(r.pred_nav)}</td>
              <td class="num">${r.actual_nav == null ? "等待净值更新" : formatNav(r.actual_nav)}</td>
              <td class="num ${getCnReturnClass(predRet)}">${formatSignedPctCN(predRet)}</td>
              <td class="num ${getCnReturnClass(actual)}">${actual == null ? "等待净值更新" : formatSignedPctCN(actual)}</td>
              <td class="num">${formatBp(r.abs_error_bp ?? ((num(r.abs_error) ?? 0) * 10000), 1)}</td>
              <td class="num">${formatPct(r.p_up, 1)}</td>
              <td>${signalText(r.direction_signal)}</td>
              <td>${r.strong_signal ? "是" : "否"}</td>
              <td>${r.direction_correct == null ? "-" : r.direction_correct ? "是" : "否"}</td>
              <td>${r.covered_80 == null ? "-" : r.covered_80 ? "80" : "未覆盖"} / ${r.covered_90 == null ? "-" : r.covered_90 ? "90" : "未覆盖"}</td>
              <td>${r.proxy_quality_flag || "-"}</td>
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `;
}

function renderPrediction(data) {
  if ($("latestRequestId")) $("latestRequestId").textContent = data.request_id || "暂无";
  renderUsabilityCard(data);
  renderCoreMetrics(data);
  renderDirectionCard(data);
  renderProxyCard(data);
  renderExcessSignalsCard(data);
  renderModelMonitoringCard(data);
  renderHealthCard(data);
  renderHistoryTable(data.prediction_history || []);
}

function chartSeriesConfig(rows) {
  const visible = {};
  document.querySelectorAll(".chart-toggles input").forEach((el) => {
    visible[el.dataset.series] = el.checked;
  });
  const series = [];
  if (visible["实际收益"]) {
    series.push({ name: "实际收益", type: "line", data: rows.map(r => r.target_next ?? r.actual), showSymbol: false, lineStyle: { width: 2.4 } });
  }
  if (visible["点预测"]) {
    series.push({ name: "点预测", type: "line", data: rows.map(r => r.pred_return ?? r.pred), showSymbol: false, lineStyle: { width: 1.5 } });
  }
  if (visible["rolling_mean"]) {
    series.push({ name: "rolling_mean", type: "line", data: rows.map(r => r.rolling_mean_baseline), showSymbol: false, lineStyle: { type: "dashed" } });
    series.push({ name: "zero", type: "line", data: rows.map(() => 0), showSymbol: false, lineStyle: { type: "dotted" } });
  }
  if (visible["p_up"]) {
    series.push({ name: "p_up", type: "line", yAxisIndex: 1, data: rows.map(r => r.p_up), showSymbol: false });
    series.push({
      name: "强信号点",
      type: "scatter",
      data: rows.map((r, i) => r.strong_signal ? [i, r.target_next ?? r.actual] : null).filter(Boolean),
      symbolSize: 8,
    });
  }
  return series;
}

function renderChart(rows) {
  if (!window.echarts || !$("chart")) return;
  if (!currentChart) currentChart = echarts.init($("chart"));
  currentChart.setOption({
    tooltip: {
      trigger: "axis",
      valueFormatter: (v) => typeof v === "number" ? `${(v * 100).toFixed(2)}%` : v,
    },
    legend: { top: 0 },
    grid: { left: 48, right: 52, top: 44, bottom: 36 },
    xAxis: { type: "category", data: rows.map(r => r.date || r.asof_date) },
    yAxis: [
      { type: "value", axisLabel: { formatter: v => `${(v * 100).toFixed(1)}%` } },
      { type: "value", min: 0, max: 1, axisLabel: { formatter: v => `${(v * 100).toFixed(0)}%` } },
    ],
    series: chartSeriesConfig(rows),
  }, true);
}

async function loadBacktest(code) {
  try {
    const res = await api(`/api/fund/${code}/backtest`);
    lastBacktestRows = res.data || [];
    renderChart(lastBacktestRows);
  } catch (err) {
    console.error("loadBacktest failed", err);
  }
}

async function loadModelInfo(code) {
  try {
    const res = await api(`/api/fund/${code}/model`);
    const history = res.data?.prediction_history || res.data?.history || [];
    renderHistoryTable(history);
  } catch (err) {
    console.error("loadModelInfo failed", err);
  }
}

async function predict(options = {}) {
  clearError();
  setBusy(true);
  setStatus("正在加载模型并预测。");
  try {
    const code = fundCode();
    const forceRetrain = options.forceRetrain ?? ($("forceRetrain")?.checked || false);
    const res = await api("/api/fund/predict", {
      method: "POST",
      body: JSON.stringify({ fund_code: code, force_retrain: forceRetrain }),
    });
    renderPrediction(res.data);
    await Promise.all([loadBacktest(code), loadModelInfo(code)]);
    setStatus("预测完成。");
  } catch (err) {
    if (err?.code === "MODEL_NOT_FOUND") setStatus("该基金尚未训练，请点击训练并预测。");
    if (err?.code === "MODEL_TRAINING_FAILED") setStatus("上一次训练失败，模型未保存，请查看日志。");
    showError(err);
  } finally {
    setBusy(false);
  }
}

async function trainAndPredict() {
  clearError();
  setBusy(true);
  setProgress(0, "queued", "提交训练任务");
  try {
    const res = await api("/api/train", {
      method: "POST",
      body: JSON.stringify({ fund_code: fundCode(), force: true }),
    });
    const taskId = res.task_id;
    setStatus(`训练任务已提交：${taskId}`);
    const timer = setInterval(async () => {
      try {
        const task = (await api(`/api/tasks/${taskId}`)).data;
        setProgress(task.progress, task.stage, task.message, task.status);
        if (task.status === "success" || task.status === "completed") {
          clearInterval(timer);
          setProgress(100, "completed", "训练完成", "completed");
          setStatus("训练完成，正在自动预测。");
          setBusy(false);
          await predict({ forceRetrain: false });
        }
        if (task.status === "failed") {
          clearInterval(timer);
          setBusy(false);
          showError({
            code: task.error_code,
            message: task.error_message || task.message,
            stage: task.stage,
            task_id: task.task_id,
            details: task.details || {},
          });
        }
      } catch (err) {
        clearInterval(timer);
        setBusy(false);
        showError(err);
      }
    }, 1600);
  } catch (err) {
    setBusy(false);
    showError(err);
  }
}

setProgress(0, "", "", "idle");
$("predictBtn")?.addEventListener("click", predict);
$("trainBtn")?.addEventListener("click", trainAndPredict);
document.querySelectorAll(".chart-toggles input").forEach((el) => {
  el.addEventListener("change", () => renderChart(lastBacktestRows));
});
window.addEventListener("resize", () => currentChart?.resize());
