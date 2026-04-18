const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL, RECENT_PRACTICE_LIMIT } = require('../../config');
const { buildGrowthInsights } = require('../../utils/practice');

const QUALITY_OPTIONS = ['全部等级', '甲', '乙', '丙'];
const QUALITY_VALUES = ['all', 'good', 'medium', 'bad'];
const DATE_OPTIONS = ['全部时间', '今天', '最近 7 天', '最近 30 天'];
const DATE_VALUES = ['all', '1d', '7d', '30d'];
const SORT_OPTIONS = ['按最新', '按最高分', '按最低分'];
const SORT_VALUES = ['latest', 'highest', 'lowest'];
const EMPTY_GROWTH = buildGrowthInsights([]);

function getScorePalette(score) {
  if (score >= 85) {
    return {
      scoreColor: '#3f8451',
      scoreSoft: 'rgba(224, 241, 226, 0.96)',
    };
  }
  if (score >= 70) {
    return {
      scoreColor: '#ab6d2f',
      scoreSoft: 'rgba(247, 232, 208, 0.96)',
    };
  }
  return {
    scoreColor: '#b34b3e',
    scoreSoft: 'rgba(252, 227, 221, 0.96)',
  };
}

function getQualityLabel(level) {
  if (level === 'good') return '甲';
  if (level === 'bad') return '丙';
  return '乙';
}

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

function buildFeedbackPreview(text) {
  if (!text) return '暂无评语';
  return text.length > 42 ? `${text.slice(0, 42)}...` : text;
}

function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function buildDimensionSummary(dimensionScores = null) {
  if (!dimensionScores) return '暂无四维解释';
  const entries = Object.entries(dimensionScores)
    .filter(([, score]) => score !== null && score !== undefined)
    .map(([key, score]) => ({ key, score: Number(score) }));

  if (!entries.length) {
    return '暂无四维解释';
  }

  const labels = {
    structure: '结构',
    stroke: '笔画',
    integrity: '完整',
    stability: '稳定',
  };
  const strongest = [...entries].sort((left, right) => right.score - left.score)[0];
  const weakest = [...entries].sort((left, right) => left.score - right.score)[0];
  return `强项 ${labels[strongest.key]} ${strongest.score} / 待提升 ${labels[weakest.key]} ${weakest.score}`;
}

function normalizeSummary(summary = {}) {
  const qualityCounts = summary.quality_counts || {};
  const topCharacter = (summary.top_characters && summary.top_characters[0]) || null;
  const topDevice = (summary.top_devices && summary.top_devices[0]) || null;
  const progressDelta =
    summary.progress_delta === null || summary.progress_delta === undefined
      ? null
      : Number(summary.progress_delta);

  let progressLabel = '等待最近两周的数据对比';
  if (progressDelta !== null) {
    if (progressDelta > 0) {
      progressLabel = `近 7 天较前一周提升 ${progressDelta.toFixed(1)} 分`;
    } else if (progressDelta < 0) {
      progressLabel = `近 7 天较前一周回落 ${Math.abs(progressDelta).toFixed(1)} 分`;
    } else {
      progressLabel = '近两周平均分基本持平';
    }
  }

  return {
    total: summary.total || 0,
    averageText: formatNumber(summary.average_score),
    recentAverageText: formatNumber(summary.recent_average),
    bestScoreText: formatNumber(summary.best_score),
    latestScoreText: formatNumber(summary.latest_score),
    qualifiedRateText: formatPercent(summary.qualified_rate),
    excellentRateText: formatPercent(summary.excellent_rate),
    deviceCount: summary.device_count || 0,
    uniqueCharacters: summary.unique_characters || 0,
    recentTotal: summary.recent_total || 0,
    progressLabel,
    progressTrend: summary.progress_trend || 'flat',
    qualityCounts: {
      good: qualityCounts.good || 0,
      medium: qualityCounts.medium || 0,
      bad: qualityCounts.bad || 0,
    },
    topCharacterText: topCharacter ? `${topCharacter.character_name} · ${topCharacter.count} 次` : '暂无',
    topDeviceText: topDevice ? `${topDevice.device_name} · ${topDevice.count} 条` : '暂无',
    insight: summary.insight || '完成评测后，这里会自动生成统计总结。',
  };
}

function normalizeResult(item) {
  const palette = getScorePalette(item.total_score || 0);
  return {
    ...item,
    ...palette,
    qualityLabel: item.quality_label || getQualityLabel(item.quality_level),
    characterLabel: item.character_name || '未识别',
    deviceLabel: item.device_name || 'InkPi 设备',
    feedbackPreview: buildFeedbackPreview(item.feedback),
    ocrText: formatConfidence(item.ocr_confidence),
    qualityText: formatConfidence(item.quality_confidence),
    dimensionSummary: buildDimensionSummary(item.dimension_scores),
  };
}

Page({
  data: {
    loading: true,
    batchDeleting: false,
    results: [],
    user: null,
    userLabel: 'InkPi 演示账号',
    error: '',
    lastUpdated: '',
    deletingId: null,
    summary: normalizeSummary(),
    growthSummary: EMPTY_GROWTH.growthSummary,
    milestoneCards: EMPTY_GROWTH.milestoneCards,
    focusDimension: null,
    practicePreview: [],
    practiceSteps: EMPTY_GROWTH.sessionPlan.actions.slice(0, 2),
    managing: false,
    selectedIds: [],
    qualityOptions: QUALITY_OPTIONS,
    dateOptions: DATE_OPTIONS,
    sortOptions: SORT_OPTIONS,
    deviceOptions: ['全部设备'],
    deviceValues: ['all'],
    filters: {
      keyword: '',
      qualityIndex: 0,
      dateIndex: 0,
      sortIndex: 0,
      deviceIndex: 0,
    },
    hasActiveFilters: false,
  },

  onShow() {
    const user = auth.getUser();
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.setData({
      user,
      userLabel: (user && (user.display_name || user.username)) || 'InkPi 演示账号',
    });
    this.loadDashboard();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  onPullDownRefresh() {
    this.loadDashboard().finally(() => wx.stopPullDownRefresh());
  },

  startPolling() {
    this.stopPolling();
    this.timer = setInterval(() => {
      this.loadDashboard(true);
    }, POLL_INTERVAL);
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  buildFilterParams() {
    const { filters, deviceValues } = this.data;
    return {
      keyword: (filters.keyword || '').trim(),
      quality_level: QUALITY_VALUES[filters.qualityIndex] || 'all',
      date_range: DATE_VALUES[filters.dateIndex] || 'all',
      sort: SORT_VALUES[filters.sortIndex] || 'latest',
      device_name: deviceValues[filters.deviceIndex] || 'all',
    };
  },

  updateFilterState(patch) {
    const filters = { ...this.data.filters, ...patch };
    const params = {
      keyword: (filters.keyword || '').trim(),
      qualityLevel: QUALITY_VALUES[filters.qualityIndex] || 'all',
      dateRange: DATE_VALUES[filters.dateIndex] || 'all',
      sort: SORT_VALUES[filters.sortIndex] || 'latest',
      deviceName: this.data.deviceValues[filters.deviceIndex] || 'all',
    };

    const hasActiveFilters =
      !!params.keyword ||
      params.qualityLevel !== 'all' ||
      params.dateRange !== 'all' ||
      params.sort !== 'latest' ||
      params.deviceName !== 'all';

    this.setData({ filters, hasActiveFilters });
  },

  async loadDashboard(silent = false) {
    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const params = this.buildFilterParams();
      const [summaryPayload, historyPayload, growthPayload] = await Promise.all([
        api.getHistorySummary(params),
        api.getHistory({ ...params, limit: 80 }),
        api.getHistory({ sort: 'latest', limit: RECENT_PRACTICE_LIMIT }),
      ]);

      const normalizedSummary = normalizeSummary(summaryPayload.summary || {});
      const availableDevices = (summaryPayload.summary && summaryPayload.summary.available_devices) || [];
      const deviceOptions = ['全部设备', ...availableDevices];
      const deviceValues = ['all', ...availableDevices];

      let deviceIndex = this.data.filters.deviceIndex;
      const currentDevice = this.data.deviceValues[this.data.filters.deviceIndex] || 'all';
      const nextIndex = deviceValues.indexOf(currentDevice);
      if (nextIndex >= 0) {
        deviceIndex = nextIndex;
      } else {
        deviceIndex = 0;
      }

      const nextFilters = {
        ...this.data.filters,
        deviceIndex,
      };
      const hasActiveFilters =
        !!(nextFilters.keyword || '').trim() ||
        (QUALITY_VALUES[nextFilters.qualityIndex] || 'all') !== 'all' ||
        (DATE_VALUES[nextFilters.dateIndex] || 'all') !== 'all' ||
        (SORT_VALUES[nextFilters.sortIndex] || 'latest') !== 'latest' ||
        (deviceValues[nextFilters.deviceIndex] || 'all') !== 'all';

      const results = (historyPayload.items || []).map(normalizeResult);
      const growthInsights = buildGrowthInsights((growthPayload && growthPayload.items) || []);

      this.setData({
        results,
        summary: normalizedSummary,
        growthSummary: growthInsights.growthSummary,
        milestoneCards: growthInsights.milestoneCards,
        focusDimension: growthInsights.dimensionInsights.focusDimension,
        practicePreview: growthInsights.recommendations.slice(0, 2),
        practiceSteps: growthInsights.sessionPlan.actions.slice(0, 2),
        error: '',
        lastUpdated: this.formatTime(new Date()),
        deviceOptions,
        deviceValues,
        filters: nextFilters,
        hasActiveFilters,
        selectedIds: [],
      });
    } catch (error) {
      this.setData({ error: '拉取云端记录失败，请检查后端服务是否已经启动。' });
    } finally {
      this.setData({ loading: false, deletingId: null, batchDeleting: false });
    }
  },

  formatTime(date) {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    const hour = `${date.getHours()}`.padStart(2, '0');
    const minute = `${date.getMinutes()}`.padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${minute}`;
  },

  onKeywordInput(event) {
    this.updateFilterState({ keyword: event.detail.value });
  },

  applyKeywordFilter() {
    this.loadDashboard();
  },

  onQualityChange(event) {
    this.updateFilterState({ qualityIndex: Number(event.detail.value) });
    this.loadDashboard();
  },

  onDateChange(event) {
    this.updateFilterState({ dateIndex: Number(event.detail.value) });
    this.loadDashboard();
  },

  onSortChange(event) {
    this.updateFilterState({ sortIndex: Number(event.detail.value) });
    this.loadDashboard();
  },

  onDeviceChange(event) {
    this.updateFilterState({ deviceIndex: Number(event.detail.value) });
    this.loadDashboard();
  },

  clearFilters() {
    this.setData({
      filters: {
        keyword: '',
        qualityIndex: 0,
        dateIndex: 0,
        sortIndex: 0,
        deviceIndex: 0,
      },
      hasActiveFilters: false,
    });
    this.loadDashboard();
  },

  openDetail(event) {
    if (this.data.managing) {
      return;
    }
    const { id } = event.currentTarget.dataset;
    wx.navigateTo({ url: `/pages/result/index?id=${id}` });
  },

  goStats() {
    wx.navigateTo({ url: '/pages/stats/index' });
  },

  goPractice() {
    wx.navigateTo({ url: '/pages/practice/index' });
  },

  toggleManageMode() {
    this.setData({
      managing: !this.data.managing,
      selectedIds: [],
    });
  },

  onSelectRecord(event) {
    const { id } = event.currentTarget.dataset;
    const selected = new Set(this.data.selectedIds);
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      selected.add(id);
    }
    this.setData({ selectedIds: Array.from(selected) });
  },

  selectAllRecords() {
    const ids = this.data.results.map((item) => item.id);
    this.setData({ selectedIds: ids });
  },

  clearSelection() {
    this.setData({ selectedIds: [] });
  },

  async deleteRecord(event) {
    const { id, character } = event.currentTarget.dataset;
    const modal = await new Promise((resolve) => {
      wx.showModal({
        title: '删除记录',
        content: `确认删除“${character || '未识别'}”这条历史记录吗？`,
        confirmColor: '#b34b3e',
        success: resolve,
        fail: () => resolve({ confirm: false }),
      });
    });

    if (!modal.confirm) {
      return;
    }

    this.setData({ deletingId: id });
    try {
      await api.deleteHistory(id);
      wx.showToast({ title: '已删除', icon: 'success' });
      await this.loadDashboard(true);
    } catch (error) {
      this.setData({ deletingId: null });
      wx.showToast({ title: '删除失败', icon: 'none' });
    }
  },

  async batchDeleteSelected() {
    const ids = this.data.selectedIds || [];
    if (!ids.length) {
      wx.showToast({ title: '请先选择记录', icon: 'none' });
      return;
    }

    const modal = await new Promise((resolve) => {
      wx.showModal({
        title: '批量删除',
        content: `确认删除选中的 ${ids.length} 条记录吗？`,
        confirmColor: '#b34b3e',
        success: resolve,
        fail: () => resolve({ confirm: false }),
      });
    });

    if (!modal.confirm) {
      return;
    }

    this.setData({ batchDeleting: true });
    try {
      const response = await api.batchDeleteHistory(ids);
      wx.showToast({
        title: `已清理 ${response.deleted_count || ids.length} 条`,
        icon: 'success',
      });
      this.setData({ managing: false, selectedIds: [] });
      await this.loadDashboard(true);
    } catch (error) {
      this.setData({ batchDeleting: false });
      wx.showToast({ title: '批量删除失败', icon: 'none' });
    }
  },

  logout() {
    auth.clearSession();
    getApp().globalData.user = null;
    wx.reLaunch({ url: '/pages/login/index' });
  },
});
