const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL, RECENT_PRACTICE_LIMIT } = require('../../config');
const { buildGrowthInsights } = require('../../utils/practice');
const {
  FORMAL_SUPPORT_TEXT,
  SCRIPT_OPTIONS,
  SCRIPT_VALUES,
  UNSUPPORTED_SCOPE_TEXT,
  filterResultsByScript,
} = require('../../utils/script');

const DATE_OPTIONS = ['全部时间', '今天', '最近 7 天', '最近 30 天'];
const DATE_VALUES = ['all', '1d', '7d', '30d'];
const EMPTY_GROWTH = buildGrowthInsights([]);

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 10) / 10}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 10) / 10}%`;
}

function buildRubricCatalog(definitions = {}) {
  const catalog = {};
  Object.values(definitions || {}).forEach((definition) => {
    (definition.items || []).forEach((item) => {
      catalog[item.key] = {
        key: item.key,
        label: item.label || item.key,
        weight: Number(item.weight || 0),
      };
    });
  });
  return catalog;
}

function normalizeSummary(summary = {}, rubricCatalog = {}) {
  const total = summary.total || 0;
  const distribution = summary.score_distribution || {};
  const progressDelta =
    summary.progress_delta === null || summary.progress_delta === undefined
      ? null
      : Number(summary.progress_delta);

  const scoreBands = [
    { key: '90_plus', label: '90+', count: distribution['90_plus'] || 0 },
    { key: '80_89', label: '80-89', count: distribution['80_89'] || 0 },
    { key: '70_79', label: '70-79', count: distribution['70_79'] || 0 },
    { key: 'below_70', label: '<70', count: distribution['below_70'] || 0 },
  ].map((item) => ({
    ...item,
    ratioText: total ? formatPercent((item.count / total) * 100) : '--',
    width: total ? Math.max(8, Math.round((item.count / total) * 100)) : 8,
  }));

  const rubricAverages = summary.rubric_averages || {};
  const rubricOrder = Object.keys(rubricCatalog);
  const dimensionKeys = Array.from(
    new Set([...rubricOrder.filter((key) => key in rubricAverages), ...Object.keys(rubricAverages)])
  );
  const dimensions = dimensionKeys.map((key) => {
    const score = Number(rubricAverages[key] || 0);
    return {
      key,
      label: (rubricCatalog[key] && rubricCatalog[key].label) || key,
      score: formatNumber(rubricAverages[key]),
      width: Math.max(8, Math.round(score)),
    };
  });

  const trendPoints = (summary.trend_points || []).map((item) => ({
    ...item,
    averageText: formatNumber(item.average_score),
    barHeight: item.average_score ? Math.max(12, Math.round(Number(item.average_score))) : 12,
  }));

  let progressLabel = '等待最近两周的样本对比';
  if (progressDelta !== null) {
    if (progressDelta > 0) {
      progressLabel = '较前一周继续提升';
    } else if (progressDelta < 0) {
      progressLabel = '较前一周有所回落';
    } else {
      progressLabel = '最近两周保持稳定';
    }
  }

  return {
    total,
    averageText: formatNumber(summary.average_score),
    recentAverageText: formatNumber(summary.recent_average),
    bestScoreText: formatNumber(summary.best_score),
    qualifiedRateText: formatPercent(summary.qualified_rate),
    excellentRateText: formatPercent(summary.excellent_rate),
    progressText:
      progressDelta === null ? '--' : `${progressDelta > 0 ? '+' : ''}${progressDelta.toFixed(1)} 分`,
    progressLabel,
    progressTrend: summary.progress_trend || 'flat',
    scoreBands,
    dimensions,
    trendPoints,
    topCharacters: summary.top_characters || [],
    topDevices: summary.top_devices || [],
    reviewedResultCount: summary.reviewed_result_count || 0,
    reviewRecordCount: summary.review_record_count || 0,
    pendingReviewCount: summary.pending_review_count || 0,
    reviewCoverageRateText: formatPercent(summary.review_coverage_rate),
    agreementRateText: formatPercent(summary.agreement_rate),
    averageManualScoreText: formatNumber(summary.average_manual_score),
    averageScoreGapText: formatNumber(summary.average_score_gap),
    insight: summary.insight || '完成评测后，这里会自动生成量化总结。',
  };
}

function normalizeMethodology(payload = {}) {
  const framework = payload.framework_overview || {};
  const snapshot = payload.validation_snapshot || {};
  const plan = payload.validation_plan || {};
  const currentScope = payload.current_script_scope || {};
  const supportedScripts = (payload.supported_script_labels || []).map((item) => item.label || item.key);
  const unsupportedScripts = framework.unsupported_scripts || [];

  const references = (payload.rubric_source_catalog || []).map((item) => ({
    title: item.title,
    tag: item.organization || '项目依据',
    role: item.usage || '用于界定评测边界与维度来源。',
  }));

  return {
    framework: {
      projectPosition:
        framework.project_position || '面向楷书 + 行书单字练习的辅助评测系统',
      currentScope:
        framework.current_scope || '当前版本正式支持楷书、行书单字；其他书体暂不支持。',
      boundaryNote:
        framework.boundary_note || '新标准先替换维度层与方法论层，当前 total_score 暂不切换。',
      supportScopeText: FORMAL_SUPPORT_TEXT,
      unsupportedNote: unsupportedScripts.length ? `暂不支持：${unsupportedScripts.join('、')}` : UNSUPPORTED_SCOPE_TEXT,
      targetUsers: framework.target_users || [],
      currentScripts: supportedScripts.length ? supportedScripts : ['楷书', '行书'],
      roadmapScripts: [],
      currentRubricLabel: currentScope.rubric_label || '来源化五维正式标准',
    },
    validation: {
      statusLabel: snapshot.status_label || '仍处于样本积累阶段',
      currentSampleCount: snapshot.current_sample_count || 0,
      uniqueCharacters: snapshot.unique_characters || 0,
      deviceCount: snapshot.device_count || 0,
      recentSampleCount: snapshot.recent_sample_count || 0,
      reviewedResultCount: snapshot.reviewed_result_count || 0,
      reviewRecordCount: snapshot.review_record_count || 0,
      coverageRatioText: formatPercent(snapshot.coverage_ratio),
      reviewCoverageRateText: formatPercent(snapshot.review_coverage_rate),
      agreementRateText: formatPercent(snapshot.agreement_rate),
      averageScoreGapText: formatNumber(snapshot.average_score_gap),
      labelTarget: snapshot.label_target || plan.label_target || 0,
      expertReviewTarget: snapshot.expert_review_target || plan.expert_review_target || 0,
      trialUserTarget: snapshot.trial_user_target || plan.trial_user_target || 0,
      nextMilestone: snapshot.next_milestone || plan.next_milestone || '',
      currentStage: plan.current_stage || 'Stage 2 / 来源化五维标准已接入',
      reviewPolicy: plan.manual_review_policy || [],
    },
    references,
  };
}

Page({
  data: {
    loading: true,
    error: '',
    lastUpdated: '',
    summary: normalizeSummary(),
    growthSummary: EMPTY_GROWTH.growthSummary,
    milestoneCards: EMPTY_GROWTH.milestoneCards,
    focusDimension: null,
    strongDimension: null,
    practicePreview: [],
    practiceSteps: EMPTY_GROWTH.sessionPlan.actions.slice(0, 2),
    methodology: normalizeMethodology(),
    dateOptions: DATE_OPTIONS,
    scriptOptions: SCRIPT_OPTIONS,
    deviceOptions: ['全部设备'],
    deviceValues: ['all'],
    supportScopeText: FORMAL_SUPPORT_TEXT,
    activeScriptLabel: SCRIPT_OPTIONS[0],
    filters: {
      dateIndex: 0,
      scriptIndex: 0,
      deviceIndex: 0,
    },
  },

  onShow() {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.loadStats();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  onPullDownRefresh() {
    this.loadStats().finally(() => wx.stopPullDownRefresh());
  },

  startPolling() {
    this.stopPolling();
    this.timer = setInterval(() => {
      this.loadStats(true);
    }, POLL_INTERVAL);
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  buildParams() {
    const { filters, deviceValues } = this.data;
    return {
      date_range: DATE_VALUES[filters.dateIndex] || 'all',
      script: SCRIPT_VALUES[filters.scriptIndex] || 'all',
      device_name: deviceValues[filters.deviceIndex] || 'all',
    };
  },

  async loadStats(silent = false) {
    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const params = this.buildParams();
      const [summaryPayload, methodologyPayload, historyPayload] = await Promise.all([
        api.getHistorySummary(params),
        api.getMethodology(params),
        api.getHistory({ ...params, sort: 'latest', limit: RECENT_PRACTICE_LIMIT }),
      ]);

      const rubricCatalog = buildRubricCatalog(methodologyPayload.rubric_definitions || {});
      const summary = normalizeSummary(summaryPayload.summary || {}, rubricCatalog);
      const methodology = normalizeMethodology(methodologyPayload);
      const scriptValue = params.script || 'all';
      const growthItems = filterResultsByScript((historyPayload && historyPayload.items) || [], scriptValue);
      const growthInsights = buildGrowthInsights(growthItems);
      const availableDevices = (summaryPayload.summary && summaryPayload.summary.available_devices) || [];
      const deviceOptions = ['全部设备', ...availableDevices];
      const deviceValues = ['all', ...availableDevices];
      const currentDevice = this.data.deviceValues[this.data.filters.deviceIndex] || 'all';
      const nextDeviceIndex = Math.max(deviceValues.indexOf(currentDevice), 0);
      const nextScriptLabel = SCRIPT_OPTIONS[this.data.filters.scriptIndex] || SCRIPT_OPTIONS[0];

      this.setData({
        summary,
        growthSummary: growthInsights.growthSummary,
        milestoneCards: growthInsights.milestoneCards,
        focusDimension: growthInsights.dimensionInsights.focusDimension,
        strongDimension: growthInsights.dimensionInsights.strongDimension,
        practicePreview: growthInsights.recommendations.slice(0, 2),
        practiceSteps: growthInsights.sessionPlan.actions.slice(0, 2),
        methodology,
        lastUpdated: this.formatTime(new Date()),
        deviceOptions,
        deviceValues,
        activeScriptLabel: nextScriptLabel,
        filters: {
          ...this.data.filters,
          deviceIndex: nextDeviceIndex,
        },
      });
    } catch (error) {
      this.setData({ error: '统计信息加载失败，请检查云端接口是否可用。' });
    } finally {
      this.setData({ loading: false });
    }
  },

  formatTime(date) {
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    const hour = `${date.getHours()}`.padStart(2, '0');
    const minute = `${date.getMinutes()}`.padStart(2, '0');
    return `${month}-${day} ${hour}:${minute}`;
  },

  onDateChange(event) {
    this.setData({
      filters: {
        ...this.data.filters,
        dateIndex: Number(event.detail.value),
      },
    });
    this.loadStats();
  },

  onScriptChange(event) {
    const scriptIndex = Number(event.detail.value);
    this.setData({
      filters: {
        ...this.data.filters,
        scriptIndex,
      },
      activeScriptLabel: SCRIPT_OPTIONS[scriptIndex] || SCRIPT_OPTIONS[0],
    });
    this.loadStats();
  },

  onDeviceChange(event) {
    this.setData({
      filters: {
        ...this.data.filters,
        deviceIndex: Number(event.detail.value),
      },
    });
    this.loadStats();
  },

  goHistory() {
    const pages = getCurrentPages();
    const previousPage = pages[pages.length - 2];
    if (previousPage && previousPage.route === 'pages/history/index') {
      wx.navigateBack();
      return;
    }
    wx.reLaunch({ url: '/pages/history/index' });
  },

  goPractice() {
    wx.navigateTo({ url: '/pages/practice/index' });
  },
});
