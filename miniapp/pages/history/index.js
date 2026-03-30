const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL } = require('../../config');

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
  if (level === 'good') return '好';
  if (level === 'bad') return '坏';
  return '中';
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

Page({
  data: {
    loading: true,
    results: [],
    user: null,
    userLabel: 'InkPi 演示账号',
    error: '',
    lastUpdated: '',
    summary: {
      total: 0,
      latestScore: '--',
      average: '--',
      deviceCount: 0,
    },
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
    this.loadResults();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  onPullDownRefresh() {
    this.loadResults().finally(() => wx.stopPullDownRefresh());
  },

  startPolling() {
    this.stopPolling();
    this.timer = setInterval(() => {
      this.loadResults(true);
    }, POLL_INTERVAL);
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  async loadResults(silent = false) {
    if (!silent) {
      this.setData({ loading: true, error: '' });
    }

    try {
      const data = await api.getHistory(50);
      const results = (data.items || []).map((item) => {
        const palette = getScorePalette(item.total_score || 0);
        return {
          ...item,
          ...palette,
          qualityLabel: item.quality_label || getQualityLabel(item.quality_level),
          characterLabel: item.character_name || '未识别',
          deviceLabel: item.device_name || 'InkPi 树莓派',
          feedbackPreview: buildFeedbackPreview(item.feedback),
          ocrText: formatConfidence(item.ocr_confidence),
          qualityText: formatConfidence(item.quality_confidence),
        };
      });

      const total = results.length;
      const average =
        total > 0
          ? Math.round(results.reduce((sum, item) => sum + (item.total_score || 0), 0) / total)
          : '--';
      const deviceCount = new Set(results.map((item) => item.deviceLabel)).size;

      this.setData({
        results,
        error: '',
        lastUpdated: this.formatTime(new Date()),
        summary: {
          total,
          latestScore: total > 0 ? results[0].total_score : '--',
          average,
          deviceCount,
        },
      });
    } catch (error) {
      this.setData({ error: '拉取历史结果失败，请检查云端服务是否已经启动。' });
    } finally {
      this.setData({ loading: false });
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

  openDetail(event) {
    const { id } = event.currentTarget.dataset;
    wx.navigateTo({ url: `/pages/result/index?id=${id}` });
  },

  logout() {
    auth.clearSession();
    getApp().globalData.user = null;
    wx.reLaunch({ url: '/pages/login/index' });
  },
});
