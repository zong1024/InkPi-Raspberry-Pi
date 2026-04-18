const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL, RECENT_PRACTICE_LIMIT } = require('../../config');
const { buildGrowthInsights, formatScore } = require('../../utils/practice');

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 10) / 10}%`;
}

function normalizeSummary(summary = {}) {
  return {
    total: summary.total || 0,
    recentAverageText: formatScore(summary.recent_average),
    bestScoreText: formatScore(summary.best_score),
    qualifiedRateText: formatPercent(summary.qualified_rate),
    recentTotal: summary.recent_total || 0,
  };
}

const EMPTY_GROWTH = buildGrowthInsights([]);

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
    recommendations: [],
    sessionPlan: EMPTY_GROWTH.sessionPlan,
    sourceText: '',
  },

  onLoad(options) {
    this.sourceText =
      options && options.source === 'result'
        ? '刚看完成绩单，最适合立刻安排下一轮。'
        : '';
  },

  onShow() {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.loadPracticeCenter();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  onPullDownRefresh() {
    this.loadPracticeCenter().finally(() => wx.stopPullDownRefresh());
  },

  startPolling() {
    this.stopPolling();
    this.timer = setInterval(() => {
      this.loadPracticeCenter(true);
    }, POLL_INTERVAL);
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  async loadPracticeCenter(silent = false) {
    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const [summaryPayload, historyPayload] = await Promise.all([
        api.getHistorySummary({ date_range: '30d' }),
        api.getHistory({ sort: 'latest', limit: RECENT_PRACTICE_LIMIT }),
      ]);
      const growthInsights = buildGrowthInsights(historyPayload.items || []);

      this.setData({
        summary: normalizeSummary(summaryPayload.summary || {}),
        growthSummary: growthInsights.growthSummary,
        milestoneCards: growthInsights.milestoneCards,
        focusDimension: growthInsights.dimensionInsights.focusDimension,
        strongDimension: growthInsights.dimensionInsights.strongDimension,
        recommendations: growthInsights.recommendations,
        sessionPlan: growthInsights.sessionPlan,
        lastUpdated: this.formatTime(new Date()),
        sourceText: this.sourceText,
      });
    } catch (error) {
      this.setData({ error: '练习中心加载失败，请检查云端接口是否可用。' });
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

  goHistory() {
    const pages = getCurrentPages();
    const previousPage = pages[pages.length - 2];
    if (previousPage && previousPage.route === 'pages/history/index') {
      wx.navigateBack();
      return;
    }
    wx.reLaunch({ url: '/pages/history/index' });
  },

  goStats() {
    wx.navigateTo({ url: '/pages/stats/index' });
  },
});
