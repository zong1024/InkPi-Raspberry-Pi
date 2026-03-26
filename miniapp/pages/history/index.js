const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { POLL_INTERVAL } = require('../../config');

Page({
  data: {
    loading: true,
    results: [],
    user: null,
    error: '',
    lastUpdated: '',
  },

  onShow() {
    const user = auth.getUser();
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.setData({ user });
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
      const results = (data.items || []).map((item) => ({
        ...item,
        scoreColor: item.total_score >= 85 ? '#3d8c4b' : item.total_score >= 70 ? '#b06b2d' : '#b04236',
      }));
      this.setData({
        results,
        error: '',
        lastUpdated: this.formatTime(new Date()),
      });
    } catch (error) {
      this.setData({ error: '拉取历史结果失败，请检查后端服务是否已经启动。' });
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
