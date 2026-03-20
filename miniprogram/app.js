// app.js
App({
  onLaunch: function () {
    // 初始化云开发（主通道）
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
    } else {
      wx.cloud.init({
        env: 'inkpi-cloud',
        traceUser: true,
      });
    }

    // 初始化本地配置
    this.initLocalConfig();

    // 启动时尝试检测树莓派（辅通道，不阻塞主界面）
    this.checkRaspberryPiConnection().catch(() => {});
  },

  initLocalConfig: function () {
    const savedIP = wx.getStorageSync('raspberryPiIP') || '';
    this.globalData.raspberryPiIP = savedIP;
  },

  // ===== 树莓派直连（可选辅通道） =====
  checkRaspberryPiConnection: function () {
    const ip = this.globalData.raspberryPiIP;
    if (!ip) {
      this.globalData.isConnected = false;
      this.globalData.connectionStatus = '未配置';
      this.notifyConnectionChange(false);
      return Promise.resolve(false);
    }

    this.globalData.connectionStatus = '检测中...';
    this.notifyConnectionChange(this.globalData.isConnected);

    return new Promise((resolve) => {
      wx.request({
        url: `http://${ip}:5000/api/ping`,
        method: 'GET',
        timeout: 3000,
        success: (res) => {
          if (res.statusCode === 200 && (res.data?.status === 'ok' || res.data?.ok === true)) {
            this.globalData.isConnected = true;
            this.globalData.connectionStatus = '树莓派在线';
            this.globalData.lastPingTime = Date.now();
            this.globalData.latency = res.data?.latency || 0;
            this.notifyConnectionChange(true);
            resolve(true);
          } else {
            this.handleConnectionFailed();
            resolve(false);
          }
        },
        fail: () => {
          this.handleConnectionFailed();
          resolve(false);
        }
      });
    });
  },

  handleConnectionFailed: function () {
    this.globalData.isConnected = false;
    this.globalData.connectionStatus = '树莓派离线';
    this.notifyConnectionChange(false);
  },

  setRaspberryPiIP: function (ip) {
    this.globalData.raspberryPiIP = ip;
    wx.setStorageSync('raspberryPiIP', ip);
    return this.checkRaspberryPiConnection();
  },

  // ===== 云端主通道 =====
  getHistoryFromCloud: async function () {
    const res = await wx.cloud.callFunction({
      name: 'getHistory',
      data: {
        openid: this.globalData.openid,
        username: this.globalData.userInfo?.username
      }
    });
    return res?.result?.data || [];
  },

  getDetailFromCloud: async function (id) {
    const res = await wx.cloud.callFunction({
      name: 'getDetail',
      data: { id }
    });
    return res?.result?.data || null;
  },

  getStatsFromCloud: async function () {
    const res = await wx.cloud.callFunction({
      name: 'getStats',
      data: {
        openid: this.globalData.openid,
        username: this.globalData.userInfo?.username
      }
    });
    return res?.result?.data || {};
  },

  // ===== 统一数据入口：云优先，树莓派兜底 =====
  getEvaluationHistory: async function () {
    // 1) 云端优先
    try {
      const cloudData = await this.getHistoryFromCloud();
      if (Array.isArray(cloudData) && cloudData.length >= 0) {
        return { source: 'cloud', data: cloudData };
      }
    } catch (e) {
      console.warn('云端历史获取失败，尝试树莓派直连', e);
    }

    // 2) 树莓派兜底（可选）
    if (this.globalData.isConnected && this.globalData.raspberryPiIP) {
      try {
        const localData = await new Promise((resolve, reject) => {
          wx.request({
            url: `http://${this.globalData.raspberryPiIP}:5000/api/history`,
            method: 'GET',
            timeout: 5000,
            success: (res) => {
              if (res.statusCode === 200) resolve(res.data || []);
              else reject(new Error('树莓派历史接口异常'));
            },
            fail: reject
          });
        });
        return { source: 'raspberrypi', data: localData };
      } catch (e) {
        console.warn('树莓派历史获取失败', e);
      }
    }

    // 3) 全失败返回空
    return { source: 'none', data: [] };
  },

  // ===== 连接状态订阅 =====
  notifyConnectionChange: function (isConnected) {
    if (this.connectionCallbacks) {
      this.connectionCallbacks.forEach(callback => callback(isConnected));
    }
  },

  onConnectionChange: function (callback) {
    if (!this.connectionCallbacks) {
      this.connectionCallbacks = [];
    }
    this.connectionCallbacks.push(callback);

    return () => {
      const index = this.connectionCallbacks.indexOf(callback);
      if (index > -1) {
        this.connectionCallbacks.splice(index, 1);
      }
    };
  },

  globalData: {
    userInfo: null,
    openid: '',
    raspberryPiIP: '',
    isConnected: false,
    connectionStatus: '未配置',
    lastPingTime: null,
    latency: 0
  }
});