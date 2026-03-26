const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  data: {
    loading: true,
    result: null,
    dimensions: [],
    error: '',
  },

  onLoad(options) {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.resultId = options.id;
    this.loadDetail();
  },

  onPullDownRefresh() {
    this.loadDetail().finally(() => wx.stopPullDownRefresh());
  },

  async loadDetail() {
    this.setData({ loading: true, error: '' });
    try {
      const data = await api.getResultDetail(this.resultId);
      const result = data.result;
      const dimensions = Object.keys(result.detail_scores || {}).map((name) => ({
        name,
        value: result.detail_scores[name],
      }));
      this.setData({ result, dimensions });
    } catch (error) {
      this.setData({ error: '加载详情失败，请返回历史页后重试。' });
    } finally {
      this.setData({ loading: false });
    }
  },
});
