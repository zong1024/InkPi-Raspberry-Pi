const { API_BASE_URL, POLL_INTERVAL } = require('./config');

App({
  globalData: {
    apiBaseUrl: API_BASE_URL,
    pollInterval: POLL_INTERVAL,
    user: null,
  },

  onLaunch() {
    const token = wx.getStorageSync('inkpi_token');
    const user = wx.getStorageSync('inkpi_user');
    if (token && user) {
      this.globalData.user = user;
    }
  },
});
