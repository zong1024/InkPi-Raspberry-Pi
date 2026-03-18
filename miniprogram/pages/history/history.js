// pages/history/history.js
const app = getApp();

Page({
  data: {
    loading: true,
    historyList: [],
    isConnected: false,
    connectionStatus: '未配置'
  },

  onLoad: function (options) {
    // 监听连接状态变化
    this.unregisterCallback = app.onConnectionChange((isConnected) => {
      this.updateConnectionStatus();
    });
    
    this.loadHistory();
  },

  onShow: function () {
    // 每次显示页面时更新状态和数据
    this.updateConnectionStatus();
    this.loadHistory();
  },

  onUnload: function () {
    if (this.unregisterCallback) {
      this.unregisterCallback();
    }
  },

  // 更新连接状态
  updateConnectionStatus: function () {
    this.setData({
      isConnected: app.globalData.isConnected,
      connectionStatus: app.globalData.connectionStatus
    });
  },

  // 跳转到首页连接
  goToIndex: function () {
    wx.switchTab({
      url: '/pages/index/index'
    });
  },

  // 加载历史记录
  loadHistory: async function () {
    this.setData({ loading: true });

    try {
      // 优先从树莓派获取数据
      if (app.globalData.isConnected) {
        const historyData = await app.getEvaluationHistory();
        const formattedList = historyData.map(item => ({
          ...item,
          date: this.formatDate(item.timestamp)
        }));
        
        this.setData({
          loading: false,
          historyList: formattedList
        });
        return;
      }

      // 如果未连接，尝试从云端获取
      const res = await wx.cloud.callFunction({
        name: 'getHistory',
        data: {
          openid: app.globalData.openid,
          username: app.globalData.userInfo?.username
        }
      });

      const historyList = res.result.data || [];
      
      // 格式化日期
      const formattedList = historyList.map(item => ({
        ...item,
        date: this.formatDate(item.timestamp)
      }));

      this.setData({
        loading: false,
        historyList: formattedList
      });
    } catch (err) {
      console.error('获取历史记录失败', err);
      this.setData({ loading: false });
      
      // 如果获取失败，显示模拟数据
      this.setData({
        historyList: [
          {
            _id: 'demo1',
            title: '九成宫醴泉铭 · 每日评测',
            totalScore: 92,
            date: '2026-03-12',
            imageUrl: '/images/sample1.png'
          },
          {
            _id: 'demo2',
            title: '勤礼碑 · 局部临摹',
            totalScore: 85,
            date: '2026-03-11',
            imageUrl: '/images/sample2.png'
          }
        ]
      });
    }
  },

  // 格式化日期
  formatDate: function (timestamp) {
    const date = new Date(timestamp);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  // 查看详情
  onViewDetail: function (e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`
    });
  },

  // 返回首页
  onBack: function () {
    wx.switchTab({
      url: '/pages/index/index'
    });
  },

  // 下拉刷新
  onPullDownRefresh: function () {
    this.loadHistory().then(() => {
      wx.stopPullDownRefresh();
    });
  }
});