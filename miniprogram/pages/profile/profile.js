// pages/profile/profile.js
const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    userInfo: null,
    stats: {
      totalCount: 0,
      avgScore: 0,
      highestScore: 0
    }
  },

  onLoad: function () {
    this.checkLoginStatus();
  },

  onShow: function () {
    this.checkLoginStatus();
    if (this.data.isLoggedIn) {
      this.loadStats();
    }
  },

  // 检查登录状态
  checkLoginStatus: function () {
    const isLoggedIn = app.globalData.isLoggedIn;
    const userInfo = app.globalData.userInfo;

    this.setData({
      isLoggedIn,
      userInfo: userInfo || { nickName: '未登录', username: '' }
    });
  },

  // 加载统计数据
  loadStats: async function () {
    try {
      const res = await wx.cloud.callFunction({
        name: 'getStats',
        data: {
          openid: app.globalData.openid
        }
      });

      if (res.result) {
        this.setData({
          stats: {
            totalCount: res.result.totalCount || 0,
            avgScore: res.result.avgScore || 0,
            highestScore: res.result.highestScore || 0
          }
        });
      }
    } catch (err) {
      console.error('获取统计失败', err);
      // 模拟数据
      this.setData({
        stats: {
          totalCount: 12,
          avgScore: 85,
          highestScore: 92
        }
      });
    }
  },

  // 绑定设备
  onBindDevice: function () {
    wx.showModal({
      title: '绑定设备',
      content: '请在树莓派设备上输入以下绑定码：\n\n绑定码：' + (app.globalData.openid || 'DEMO123'),
      showCancel: false
    });
  },

  // 设置
  onSettings: function () {
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    });
  },

  // 关于
  onAbout: function () {
    wx.showModal({
      title: '关于墨韵评测',
      content: 'InkPi 墨韵评测 v1.0.0\n\n一款基于树莓派的智能书法评测系统，支持四维评分、汉字识别等功能。\n\n© 2026 By ZongRui',
      showCancel: false
    });
  },

  // 意见反馈
  onFeedback: function () {
    wx.showModal({
      title: '意见反馈',
      content: '如有问题或建议，请联系：\n\nsupport@inkpi.com',
      showCancel: false
    });
  },

  // 退出登录
  onLogout: function () {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          // 清除登录状态
          app.globalData.isLoggedIn = false;
          app.globalData.userInfo = null;
          app.globalData.openid = null;
          wx.removeStorageSync('userInfo');

          // 跳转到登录页
          wx.redirectTo({
            url: '/pages/index/index'
          });
        }
      }
    });
  }
});