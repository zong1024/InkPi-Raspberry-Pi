const state = {
  view: "overview",
  bootstrap: null,
  history: [],
  selectedRecordId: null,
  previewTimer: null,
};

const els = {
  navButtons: [...document.querySelectorAll(".nav-button")],
  views: [...document.querySelectorAll(".view")],
  cameraStatusText: document.getElementById("cameraStatusText"),
  recordCountText: document.getElementById("recordCountText"),
  averageScoreText: document.getElementById("averageScoreText"),
  pageKicker: document.getElementById("pageKicker"),
  pageTitle: document.getElementById("pageTitle"),
  modePill: document.getElementById("modePill"),
  timePill: document.getElementById("timePill"),
  globalBanner: document.getElementById("globalBanner"),
  latestScoreText: document.getElementById("latestScoreText"),
  latestCharacterText: document.getElementById("latestCharacterText"),
  latestLevelText: document.getElementById("latestLevelText"),
  summaryMetrics: document.getElementById("summaryMetrics"),
  latestResultCard: document.getElementById("latestResultCard"),
  captureStatusPill: document.getElementById("captureStatusPill"),
  cameraPreview: document.getElementById("cameraPreview"),
  guidancePanel: document.getElementById("guidancePanel"),
  captureButton: document.getElementById("captureButton"),
  uploadButton: document.getElementById("uploadButton"),
  fileInput: document.getElementById("fileInput"),
  historyList: document.getElementById("historyList"),
  historyDetail: document.getElementById("historyDetail"),
  refreshHistoryButton: document.getElementById("refreshHistoryButton"),
  historyItemTemplate: document.getElementById("historyItemTemplate"),
};

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  tickClock();
  setInterval(tickClock, 30_000);
  loadBootstrap();
});

function bindEvents() {
  els.navButtons.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  document.querySelectorAll("[data-jump]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.jump));
  });

  els.captureButton.addEventListener("click", evaluateCapture);
  els.uploadButton.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", handleUpload);
  els.refreshHistoryButton.addEventListener("click", loadHistory);
}

async function loadBootstrap() {
  try {
    const data = await fetchJson("/api/bootstrap");
    state.bootstrap = data;
    state.history = data.history || [];
    renderBootstrap();
    renderHistory();
    renderLatestResult(data.last_result || state.history[0] || null);
    switchView(state.view);
  } catch (error) {
    showBanner(`初始化失败：${error.message}`, true);
  }
}

async function loadHistory() {
  try {
    const payload = await fetchJson("/api/history?limit=60");
    state.history = payload.items || [];
    renderHistory();
    if (state.selectedRecordId) {
      await loadRecordDetail(state.selectedRecordId);
    }
  } catch (error) {
    showBanner(`刷新历史失败：${error.message}`, true);
  }
}

function renderBootstrap() {
  const { app, camera, stats, history } = state.bootstrap;
  els.cameraStatusText.textContent = camera.online ? "在线" : "离线";
  els.recordCountText.textContent = String(stats.total_count);
  els.averageScoreText.textContent = String(stats.average_score);
  els.modePill.textContent = app.mode === "raspberry-pi" ? "树莓派本地 WebUI" : "桌面 WebUI";

  els.latestScoreText.textContent = history[0] ? `${history[0].total_score}` : "--";
  els.latestCharacterText.textContent = history[0]?.character_name || "--";
  els.latestLevelText.textContent = history[0]?.quality_label || "--";

  const metrics = [
    { label: "累计记录", value: stats.total_count },
    { label: "平均得分", value: stats.average_score || "--" },
    { label: "最高得分", value: stats.max_score || "--" },
    { label: "最低得分", value: stats.min_score || "--" },
  ];

  els.summaryMetrics.innerHTML = "";
  metrics.forEach((item) => {
    const row = document.createElement("div");
    row.className = "metric-row";
    row.innerHTML = `
      <span>${item.label}</span>
      <div class="metric-track"><div class="metric-bar" style="width:${metricWidth(item.value)}%"></div></div>
      <strong>${item.value}</strong>
    `;
    els.summaryMetrics.appendChild(row);
  });
}

function renderLatestResult(result) {
  if (!result) {
    els.latestResultCard.className = "result-summary empty-state";
    els.latestResultCard.textContent = "暂无评测结果，先去拍一张作品。";
    return;
  }

  els.latestResultCard.className = "result-summary";
  els.latestResultCard.innerHTML = `
    <div class="summary-score">
      <strong style="color:${result.color}">${result.total_score}</strong>
      <div>
        <div>${result.quality_label}</div>
        <div>${result.display_time}</div>
      </div>
    </div>
    <div class="summary-meta">
      <span>识别字：${result.character_name}</span>
      <span>OCR：${formatConfidence(result.ocr_confidence)}</span>
    </div>
    <p>${result.feedback}</p>
  `;
}

function renderHistory() {
  els.historyList.innerHTML = "";
  if (!state.history.length) {
    els.historyList.innerHTML = `<div class="empty-state">暂无历史记录，先完成一次评测。</div>`;
    return;
  }

  state.history.forEach((item, index) => {
    const node = els.historyItemTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".history-char").textContent = item.character_name;
    node.querySelector(".history-style").textContent = `等级 ${item.quality_label} / OCR ${formatConfidence(item.ocr_confidence)}`;
    node.querySelector(".history-score").textContent = item.total_score;
    node.querySelector(".history-time").textContent = item.display_time;
    if (item.id === state.selectedRecordId || (!state.selectedRecordId && index === 0)) {
      node.classList.add("is-active");
      state.selectedRecordId = item.id;
      renderHistoryDetail(item);
    }
    node.addEventListener("click", async () => {
      state.selectedRecordId = item.id;
      renderHistory();
      await loadRecordDetail(item.id);
    });
    els.historyList.appendChild(node);
  });
}

async function loadRecordDetail(recordId) {
  try {
    const detail = await fetchJson(`/api/results/${recordId}`);
    renderHistoryDetail(detail);
  } catch (error) {
    showBanner(`读取结果详情失败：${error.message}`, true);
  }
}

function renderHistoryDetail(item) {
  if (!item) {
    els.historyDetail.className = "detail-panel empty-state";
    els.historyDetail.textContent = "选择左侧一条记录查看完整详情。";
    return;
  }

  const originalImage = item.id ? `/api/results/${item.id}/image/original` : "";
  els.historyDetail.className = "detail-panel";
  els.historyDetail.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h4>${item.character_name}</h4>
        <p>${item.quality_label} / OCR ${formatConfidence(item.ocr_confidence)} / ${item.display_time}</p>
      </div>
      <div class="detail-score" style="color:${item.color}">${item.total_score}</div>
    </div>
    ${originalImage ? `<img src="${originalImage}" alt="作品原图" style="width:100%;border-radius:22px;max-height:280px;object-fit:cover;">` : ""}
    <div class="summary-meta">
      <span>质量置信度：${formatConfidence(item.quality_confidence)}</span>
      <span>自动识别：${item.character_name}</span>
    </div>
    <p class="detail-feedback">${item.feedback}</p>
  `;
}

function switchView(view) {
  state.view = view;
  els.navButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  els.views.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === view);
  });

  const pageMeta = {
    overview: ["演示主控台", "自动评测总览"],
    capture: ["自动识别优先", "拍照评测"],
    history: ["结果归档", "历史记录"],
  };
  const [kicker, title] = pageMeta[view];
  els.pageKicker.textContent = kicker;
  els.pageTitle.textContent = title;

  if (view === "capture") {
    startPreviewLoop();
  } else {
    stopPreviewLoop();
  }
}

function startPreviewLoop() {
  stopPreviewLoop();
  refreshCameraFrame();
  state.previewTimer = setInterval(refreshCameraFrame, 1200);
}

function stopPreviewLoop() {
  if (state.previewTimer) {
    clearInterval(state.previewTimer);
    state.previewTimer = null;
  }
}

function refreshCameraFrame() {
  const stamp = Date.now();
  els.cameraPreview.src = `/api/camera/frame?ts=${stamp}`;
  els.cameraPreview.onerror = () => {
    els.captureStatusPill.textContent = "摄像头离线";
  };
  els.cameraPreview.onload = () => {
    els.captureStatusPill.textContent = "实时在线";
  };
}

async function evaluateCapture() {
  setBusy(true, "正在拍照并评测，请稍候…");
  try {
    const payload = await fetchJson("/api/evaluate/capture", { method: "POST" });
    const result = payload.result;
    ingestNewResult(result);
    showBanner(`评测完成：${result.character_name} / ${result.total_score} 分 / ${result.quality_label}`);
    switchView("history");
  } catch (error) {
    handleEvaluationError(error);
  } finally {
    setBusy(false);
  }
}

async function handleUpload(event) {
  const [file] = event.target.files || [];
  if (!file) {
    return;
  }

  const formData = new FormData();
  formData.append("image", file);
  setBusy(true, "正在导入图片并评测…");

  try {
    const payload = await fetchJson("/api/evaluate/upload", {
      method: "POST",
      body: formData,
    });
    const result = payload.result;
    ingestNewResult(result);
    showBanner(`图片评测完成：${result.character_name} / ${result.total_score} 分 / ${result.quality_label}`);
    switchView("history");
  } catch (error) {
    handleEvaluationError(error);
  } finally {
    event.target.value = "";
    setBusy(false);
  }
}

function ingestNewResult(result) {
  state.history = [result, ...state.history.filter((item) => item.id !== result.id)];
  state.selectedRecordId = result.id;
  renderLatestResult(result);
  renderHistory();
  renderHistoryDetail(result);
  if (state.bootstrap) {
    const total = Number(els.recordCountText.textContent || "0") + 1;
    els.recordCountText.textContent = String(total);
    els.latestScoreText.textContent = `${result.total_score}`;
    els.latestCharacterText.textContent = result.character_name;
    els.latestLevelText.textContent = result.quality_label;
  }
}

function handleEvaluationError(error) {
  if (error.payload && error.payload.guidance) {
    els.guidancePanel.textContent = `${error.payload.message} ${error.payload.guidance}`;
    showBanner(`${error.payload.message} ${error.payload.guidance}`, true);
  } else {
    showBanner(error.message, true);
  }
}

function setBusy(isBusy, text = "") {
  els.captureButton.disabled = isBusy;
  els.uploadButton.disabled = isBusy;
  els.captureStatusPill.textContent = isBusy ? "评测中" : "待机";
  if (text) {
    els.guidancePanel.textContent = text;
  }
}

function showBanner(message, isError = false) {
  els.globalBanner.textContent = message;
  els.globalBanner.classList.remove("is-hidden");
  els.globalBanner.classList.toggle("is-error", isError);
}

function tickClock() {
  const now = new Date();
  els.timePill.textContent = now.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function metricWidth(value) {
  if (value === "--") return 0;
  return Math.max(0, Math.min(100, Number(value) || 0));
}

function formatConfidence(value) {
  if (typeof value !== "number") return "--";
  return `${Math.round(value * 100)}%`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(data?.message || `请求失败：${response.status}`);
    error.payload = data;
    throw error;
  }
  return data;
}
