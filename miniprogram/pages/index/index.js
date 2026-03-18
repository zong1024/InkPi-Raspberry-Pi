// pages/index/index.js - 设备连接页
const app = getApp();

Page({
  data: {
    isConnected: false,
    connectionStatus: '未配置',
    statusDetail: '请设置树莓派 IP 地址',
    raspberryPiIP: '',
    latency: 0,
    isChecking: false,
    showIPModal: false,
    inputIP: ''
  },

  onLoad: function () {
    // 监听连接状态变化
    this.unregisterCallback = app.onConnectionChange((isConnected) => {
      this.updateConnectionStatus();
    });
  },

  onShow: function () {
    // 每次显示页面时更新状态
    this.updateConnectionStatus();
  },

  onUnload: function () {
    // 取消注册回调
    if (this.unregisterCallback) {
      this.unregisterCallback();
    }
  },

  // 更新连接状态显示
  updateConnectionStatus: function () {
    const globalData = app.globalData;
    
    let statusDetail = '';
    if (!globalData.raspberryPiIP) {
      statusDetail = '请设置树莓派 IP 地址';
    } else if (globalData.isConnected) {
      statusDetail = '树莓派已连接，可以开始评测';
    } else {
      statusDetail = '无法连接到树莓派，请检查网络';
    }

    this.setData({
      isConnected: globalData.isConnected,
      connectionStatus: globalData.connectionStatus,
      statusDetail: statusDetail,
      raspberryPiIP: globalData.raspberryPiIP,
      latency: globalData.latency
    });
  },

  // 刷新连接状态
  onRefreshStatus: async function () {
    if (this.data.isChecking) return;

    this.setData({ isChecking: true });

    try {
      await app.checkRaspberryPiConnection();
      this.updateConnectionStatus();

      if (this.data.isConnected) {
        wx.showToast({
          title: '连接成功',
          icon: 'success'
        });
      } else {
        wx.showToast({
          title: '连接失败',
          icon: 'error'
        });
      }
    } catch (err) {
      wx.showToast({
        title: '检测失败',
        icon: 'error'
      });
    } finally {
      this.setData({ isChecking: false });
    }
  },

  // 显示 IP 设置弹窗
  onShowIPSetting: function () {
    this.setData({
      showIPModal: true,
      inputIP: this.data.raspberryPiIP || ''
    });
  },

  // 隐藏 IP 设置弹窗
  onHideIPSetting: function () {
    this.setData({ showIPModal: false });
  },

  // 阻止事件冒泡
  preventClose: function () {},

  // IP 输入
  onIPInput: function (e) {
    this.setData({
      inputIP: e.detail.value
    });
  },

  // 确认 IP 设置
  onConfirmIP: async function () {
    const ip = this.data.inputIP.trim();

    if (!ip) {
      wx.showToast({
        title: '请输入 IP 地址',
        icon: 'none'
      });
      return;
    }

    // 简单验证 IP 格式
    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipPattern.test(ip)) {
      wx.showToast({
        title: 'IP 格式不正确',
        icon: 'none'
      });
      return;
    }

    wx.showLoading({ title: '连接中...' });

    try {
      const success = await app.setRaspberryPiIP(ip);
      
      wx.hideLoading();
      this.setData({ showIPModal: false });
      this.updateConnectionStatus();

      if (success) {
        wx.showToast({
          title: '连接成功',
          icon: 'success'
        });
      } else {
        wx.showToast({
          title: '连接失败，请检查 IP',
          icon: 'none',
          duration: 2000
        });
      }
    } catch (err) {
      wx.hideLoading();
      wx.showToast({
        title: '设置失败',
        icon: 'error'
      });
    }
  },

  // 跳转到历史页
  goToHistory: function () {
    wx.switchTab({
      url: '/pages/history/history'
    });
  }
});