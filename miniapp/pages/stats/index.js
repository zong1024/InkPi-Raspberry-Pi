const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL } = require('../../config');

const DATE_OPTIONS = ['全部时间', '今天', '最近 7 天', '最近 30 天'];
const DATE_VALUES = ['all', '1d', '7d', '30d'];

const DIMENSION_LABELS = {
  structure: '结构',
  stroke: '笔画',
  integrity: '完整',
  stability: '稳定',
};

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

function normalizeSummary(summary = {}) {
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

  const dimensions = Object.entries(DIMENSION_LABELS).map(([key, label]) => ({
    key,
    label,
    score: formatNumber(summary.dimension_averages && summary.dimension_averages[key]),
    width: Math.max(
      8,
      Math.round(Number((summary.dimension_averages && summary.dimension_averages[key]) || 0))
    ),
  }));

  const trendPoints = (summary.trend_points || []).map((item) => ({
    ...item,
    averageText: formatNumber(item.average_score),
    barHeight: item.average_score ? Math.max(12, Math.round(Number(item.average_score))) : 12,
  }));

  return {
    total,
    averageText: formatNumber(summary.average_score),
    recentAverageText: formatNumber(summary.recent_average),
    bestScoreText: formatNumber(summary.best_score),
    qualifiedRateText: formatPercent(summary.qualified_rate),
    excellentRateText: formatPercent(summary.excellent_rate),
    progressText:
      progressDelta === null ? '--' : `${progressDelta > 0 ? '+' : ''}${progressDelta.toFixed(1)} 分`,
    progressLabel:
      progressDelta === null
        ? '等待近两周样本'
        : progressDelta > 0
          ? '较前一周提升'
          : progressDelta < 0
            ? '较前一周回落'
            : '近两周持平',
    progressTrend: summary.progress_trend || 'flat',
    scoreBands,
    dimensions,
    trendPoints,
    topCharacters: summary.top_characters || [],
    topDevices: summary.top_devices || [],
    insight: summary.insight || '完成评测后，这里会自动生成量化总结。',
  };
}

Page({
  data: {
    loading: true,
    error: '',
    lastUpdated: '',
    summary: normalizeSummary(),
    dateOptions: DATE_OPTIONS,
    deviceOptions: ['全部设备'],
    deviceValues: ['all'],
    filters: {
      dateIndex: 0,
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
      device_name: deviceValues[filters.deviceIndex] || 'all',
    };
  },

  async loadStats(silent = false) {
    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const params = this.buildParams();
      const payload = await api.getHistorySummary(params);
      const summary = normalizeSummary(payload.summary || {});
      const availableDevices = (payload.summary && payload.summary.available_devices) || [];
      const deviceOptions = ['全部设备', ...availableDevices];
      const deviceValues = ['all', ...availableDevices];
      const currentDevice = this.data.deviceValues[this.data.filters.deviceIndex] || 'all';
      const nextDeviceIndex = Math.max(deviceValues.indexOf(currentDevice), 0);

      this.setData({
        summary,
        lastUpdated: this.formatTime(new Date()),
        deviceOptions,
        deviceValues,
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
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.reLaunch({ url: '/pages/history/index' });
  },
});
