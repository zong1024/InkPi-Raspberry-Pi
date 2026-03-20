// pages/index/index.js - 主界面（云优先，树莓派可选）
const app = getApp();

Page({
  data: {
    // 云端状态
    cloudReady: true,
    cloudStatusText: '云端可用',

    // 树莓派状态（可选）
    isConnected: false,
    connectionStatus: '未配置',
    statusDetail: '树莓派连接是可选项，不影响主功能',
    raspberryPiIP: '',
    latency: 0,
    isChecking: false,

    // UI
    showIPModal: false,
    inputIP: ''
  },

  onLoad: function () {
    this.unregisterCallback = app.onConnectionChange(() => {
      this.updateConnectionStatus();
    });
  },

  onShow: function () {
    this.updateConnectionStatus();
  },

  onUnload: function () {
    if (this.unregisterCallback) {
      this.unregisterCallback();
    }
  },

  updateConnectionStatus: function () {
    const g = app.globalData;

    let statusDetail = '树莓派连接是可选项，不影响主功能';
    if (g.raspberryPiIP && g.isConnected) {
      statusDetail = '树莓派在线，可使用局域网直连加速';
    } else if (g.raspberryPiIP && !g.isConnected) {
      statusDetail = '树莓派离线，系统将自动使用云端数据';
    }

    this.setData({
      isConnected: g.isConnected,
      connectionStatus: g.connectionStatus,
      statusDetail,
      raspberryPiIP: g.raspberryPiIP,
      latency: g.latency
    });
  },

  onRefreshStatus: async function () {
    if (this.data.isChecking) return;
    this.setData({ isChecking: true });

    try {
      const ok = await app.checkRaspberryPiConnection();
      this.updateConnectionStatus();
      wx.showToast({
        title: ok ? '树莓派在线' : '树莓派离线',
        icon: ok ? 'success' : 'none'
      });
    } catch (e) {
      wx.showToast({ title: '检测失败', icon: 'none' });
    } finally {
      this.setData({ isChecking: false });
    }
  },

  onShowIPSetting: function () {
    this.setData({
      showIPModal: true,
      inputIP: this.data.raspberryPiIP || ''
    });
  },

  onHideIPSetting: function () {
    this.setData({ showIPModal: false });
  },

  preventClose: function () {},

  onIPInput: function (e) {
    this.setData({ inputIP: e.detail.value });
  },

  onConfirmIP: async function () {
    const ip = (this.data.inputIP || '').trim();
    if (!ip) {
      wx.showToast({ title: '请输入 IP 地址', icon: 'none' });
      return;
    }

    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipPattern.test(ip)) {
      wx.showToast({ title: 'IP 格式不正确', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '保存中...' });
    try {
      await app.setRaspberryPiIP(ip);
      this.setData({ showIPModal: false });
      this.updateConnectionStatus();
      wx.showToast({ title: '已保存', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  // 直接进入主功能（不依赖树莓派）
  goToHistory: function () {
    wx.switchTab({
      url: '/pages/history/history'
    });
  }
});