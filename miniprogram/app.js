// app.js
App({
  onLaunch: function () {
    // 初始化云开发
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
    } else {
      wx.cloud.init({
        env: 'inkpi-cloud', // 云开发环境ID
        traceUser: true,
      });
    }

    // 初始化树莓派连接状态
    this.initRaspberryPiConnection();
  },

  // 初始化树莓派连接
  initRaspberryPiConnection: function () {
    // 从本地存储读取保存的 IP
    const savedIP = wx.getStorageSync('raspberryPiIP');
    if (savedIP) {
      this.globalData.raspberryPiIP = savedIP;
      // 自动检测连接
      this.checkRaspberryPiConnection();
    }
  },

  // 检测树莓派连接状态
  checkRaspberryPiConnection: function () {
    const ip = this.globalData.raspberryPiIP;
    if (!ip) {
      this.globalData.isConnected = false;
      this.globalData.connectionStatus = '未配置';
      return Promise.resolve(false);
    }

    this.globalData.connectionStatus = '检测中...';
    
    return new Promise((resolve) => {
      wx.request({
        url: `http://${ip}:5000/api/ping`,
        method: 'GET',
        timeout: 5000,
        success: (res) => {
          if (res.statusCode === 200 && res.data.status === 'ok') {
            this.globalData.isConnected = true;
            this.globalData.connectionStatus = '已连接';
            this.globalData.lastPingTime = Date.now();
            this.globalData.latency = res.data.latency || 0;
            
            // 通知所有页面更新状态
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

  // 连接失败处理
  handleConnectionFailed: function () {
    this.globalData.isConnected = false;
    this.globalData.connectionStatus = '未连接';
    this.notifyConnectionChange(false);
  },

  // 设置树莓派 IP
  setRaspberryPiIP: function (ip) {
    this.globalData.raspberryPiIP = ip;
    wx.setStorageSync('raspberryPiIP', ip);
    return this.checkRaspberryPiConnection();
  },

  // 通知连接状态变化
  notifyConnectionChange: function (isConnected) {
    // 触发事件通知页面更新
    if (this.connectionCallbacks) {
      this.connectionCallbacks.forEach(callback => callback(isConnected));
    }
  },

  // 注册连接状态回调
  onConnectionChange: function (callback) {
    if (!this.connectionCallbacks) {
      this.connectionCallbacks = [];
    }
    this.connectionCallbacks.push(callback);
    
    // 返回取消注册函数
    return () => {
      const index = this.connectionCallbacks.indexOf(callback);
      if (index > -1) {
        this.connectionCallbacks.splice(index, 1);
      }
    };
  },

  // 获取评测历史
  getEvaluationHistory: function () {
    return new Promise((resolve, reject) => {
      if (!this.globalData.isConnected) {
        reject(new Error('树莓派未连接'));
        return;
      }

      wx.request({
        url: `http://${this.globalData.raspberryPiIP}:5000/api/history`,
        method: 'GET',
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error('获取历史失败'));
          }
        },
        fail: (err) => {
          reject(err);
        }
      });
    });
  },

  globalData: {
    userInfo: null,
    raspberryPiIP: '',        // 树莓派 IP 地址
    isConnected: false,       // 是否已连接
    connectionStatus: '未配置', // 连接状态文字
    lastPingTime: null,       // 上次检测时间
    latency: 0                // 延迟 (ms)
  }
});