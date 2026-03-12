// pages/index/index.js
const app = getApp();

Page({
  data: {
    username: '',
    password: '',
    agreed: false
  },

  onLoad: function (options) {
    // 检查是否已登录
    if (app.globalData.isLoggedIn) {
      this.navigateToHistory();
    }
  },

  // 用户名输入
  onUsernameInput: function (e) {
    this.setData({
      username: e.detail.value
    });
  },

  // 密码输入
  onPasswordInput: function (e) {
    this.setData({
      password: e.detail.value
    });
  },

  // 协议勾选
  onAgreementChange: function (e) {
    this.setData({
      agreed: e.detail.value.length > 0
    });
  },

  // 登录/注册
  onLogin: async function () {
    const { username, password, agreed } = this.data;

    // 验证
    if (!username.trim()) {
      wx.showToast({ title: '请输入用户名', icon: 'none' });
      return;
    }
    if (!password.trim()) {
      wx.showToast({ title: '请输入密码', icon: 'none' });
      return;
    }
    if (password.length < 4) {
      wx.showToast({ title: '密码至少4位', icon: 'none' });
      return;
    }
    if (!agreed) {
      wx.showToast({ title: '请先同意用户协议', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '登录中...' });

    try {
      const res = await wx.cloud.callFunction({
        name: 'login',
        data: {
          username: username.trim(),
          password: password.trim()
        }
      });

      wx.hideLoading();

      if (res.result.success) {
        // 保存用户信息到全局
        app.globalData.isLoggedIn = true;
        app.globalData.userInfo = res.result.userInfo;
        app.globalData.openid = res.result.openid;

        // 保存到本地存储
        wx.setStorageSync('userInfo', res.result.userInfo);
        wx.setStorageSync('isLoggedIn', true);

        wx.showToast({
          title: res.result.isNewUser ? '注册成功' : '登录成功',
          icon: 'success'
        });

        setTimeout(() => {
          this.navigateToHistory();
        }, 1000);
      } else {
        wx.showToast({
          title: res.result.message || '登录失败',
          icon: 'none'
        });
      }
    } catch (err) {
      wx.hideLoading();
      wx.showToast({
        title: '网络错误',
        icon: 'error'
      });
      console.error('登录失败', err);
    }
  },

  // 打开协议
  onOpenAgreement: function (e) {
    wx.showModal({
      title: '用户服务协议',
      content: '欢迎使用墨韵评测小程序。本应用为书法评测工具，用户信息仅用于数据同步。',
      showCancel: false
    });
  },

  // 跳转到历史记录页
  navigateToHistory: function () {
    wx.switchTab({
      url: '/pages/history/history'
    });
  }
});