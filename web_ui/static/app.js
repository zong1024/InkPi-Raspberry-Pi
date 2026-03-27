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
  characterGrid: document.getElementById("characterGrid"),
  selectedCharacterLabel: document.getElementById("selectedCharacterLabel"),
  selectionModePill: document.getElementById("selectionModePill"),
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
  latestStyleText: document.getElementById("latestStyleText"),
  detailAverages: document.getElementById("detailAverages"),
  latestResultCard: document.getElementById("latestResultCard"),
  captureStatusPill: document.getElementById("captureStatusPill"),
  cameraPreview: document.getElementById("cameraPreview"),
  guideCaption: document.getElementById("guideCaption"),
  captureTargetTitle: document.getElementById("captureTargetTitle"),
  captureTargetCopy: document.getElementById("captureTargetCopy"),
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
  const { app, selection, camera, stats, characters, history } = state.bootstrap;
  renderCharacterGrid(characters, selection);
  updateSelection(selection);
  els.cameraStatusText.textContent = camera.online ? "在线" : "离线";
  els.recordCountText.textContent = String(stats.total_count);
  els.averageScoreText.textContent = String(stats.average_score);
  els.modePill.textContent = app.mode === "raspberry-pi" ? "树莓派本地 WebUI" : "桌面 WebUI";

  els.latestScoreText.textContent = history[0] ? `${history[0].total_score}` : "--";
  els.latestCharacterText.textContent = history[0]?.character_name || "--";
  els.latestStyleText.textContent = history[0]?.style || "--";

  els.detailAverages.innerHTML = "";
  stats.average_details.forEach((item) => {
    const row = document.createElement("div");
    row.className = "metric-row";
    row.innerHTML = `
      <span>${item.label}</span>
      <div class="metric-track"><div class="metric-bar" style="width:${Math.max(0, Math.min(100, item.score))}%"></div></div>
      <strong>${item.score}</strong>
    `;
    els.detailAverages.appendChild(row);
  });
}

function renderCharacterGrid(characters, selection) {
  els.characterGrid.innerHTML = "";

  const autoButton = document.createElement("button");
  autoButton.className = `character-chip is-auto ${selection.locked ? "" : "is-selected"}`.trim();
  autoButton.textContent = "AUTO";
  autoButton.addEventListener("click", () => updateSelectionRemote(null));
  els.characterGrid.appendChild(autoButton);

  characters.forEach((item) => {
    const chip = document.createElement("button");
    chip.className = `character-chip ${selection.key === item.key ? "is-selected" : ""}`.trim();
    chip.textContent = item.display;
    chip.title = item.styles.join(" / ");
    chip.addEventListener("click", () => updateSelectionRemote(item.key));
    els.characterGrid.appendChild(chip);
  });
}

async function updateSelectionRemote(character) {
  try {
    const selection = await fetchJson("/api/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character }),
    });
    state.bootstrap.selection = selection;
    renderCharacterGrid(state.bootstrap.characters, selection);
    updateSelection(selection);
    showBanner(selection.locked ? `已锁定评测字：${selection.display}` : "已切回自动 OCR 模式。");
  } catch (error) {
    showBanner(`设置评测字失败：${error.message}`, true);
  }
}

function updateSelection(selection) {
  els.selectedCharacterLabel.textContent = selection.display;
  els.selectionModePill.textContent = selection.locked ? "手动锁定" : "自动 OCR";
  els.captureTargetTitle.textContent = selection.display;
  els.captureTargetCopy.textContent = selection.locked
    ? `当前已锁定评测字“${selection.display}”，系统将跳过自动识别，直接按该字进入评分。`
    : "当前未锁定评测字，系统会先自动识别字符，再决定进入模板评分、通用评分或提示重拍。";
  els.guideCaption.textContent = selection.locked ? `TARGET ${selection.display}` : "AUTO";
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
        <div>${result.grade}</div>
        <div>${result.display_time}</div>
      </div>
    </div>
    <div class="summary-meta">
      <span>评测字：${result.character_name}</span>
      <span>书体：${result.style}</span>
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
    node.querySelector(".history-style").textContent = item.style;
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

  const metrics = item.details
    .map(
      (detail) => `
        <div class="metric-row">
          <span>${detail.label}</span>
          <div class="metric-track"><div class="metric-bar" style="width:${detail.score}%"></div></div>
          <strong>${detail.score}</strong>
        </div>
      `
    )
    .join("");

  const originalImage = item.id ? `/api/results/${item.id}/image/original` : "";
  els.historyDetail.className = "detail-panel";
  els.historyDetail.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h4>${item.character_name}</h4>
        <p>${item.style} · ${item.grade} · ${item.display_time}</p>
      </div>
      <div class="detail-score" style="color:${item.color}">${item.total_score}</div>
    </div>
    ${originalImage ? `<img src="${originalImage}" alt="作品原图" style="width:100%;border-radius:22px;max-height:280px;object-fit:cover;">` : ""}
    <div class="detail-metrics">${metrics}</div>
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
    overview: ["演示主控台", "评测总览"],
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
    showBanner(`评测完成：${result.character_name} · ${result.total_score} 分`);
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
    showBanner(`图片评测完成：${result.character_name} · ${result.total_score} 分`);
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
    els.latestStyleText.textContent = result.style;
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
