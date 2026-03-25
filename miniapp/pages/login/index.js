const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  data: {
    username: 'demo',
    password: 'demo123456',
    loading: false,
    error: '',
  },

  onShow() {
    if (auth.getToken()) {
      wx.reLaunch({ url: '/pages/history/index' });
    }
  },

  onInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [field]: event.detail.value, error: '' });
  },

  async onLogin() {
    const { username, password } = this.data;
    if (!username || !password) {
      this.setData({ error: '请输入账号和密码' });
      return;
    }

    this.setData({ loading: true, error: '' });
    try {
      const data = await api.login(username, password);
      auth.saveSession(data.token, data.user);
      getApp().globalData.user = data.user;
      wx.reLaunch({ url: '/pages/history/index' });
    } catch (error) {
      this.setData({ error: '登录失败，请检查账号密码或后端地址' });
    } finally {
      this.setData({ loading: false });
    }
  },
});
