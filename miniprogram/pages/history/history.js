// pages/history/history.js
const app = getApp();

Page({
  data: {
    loading: true,
    historyList: []
  },

  onLoad: function (options) {
    // 检查登录状态
    if (!app.globalData.isLoggedIn) {
      wx.redirectTo({
        url: '/pages/index/index'
      });
      return;
    }
    this.loadHistory();
  },

  onShow: function () {
    // 每次显示页面时刷新数据
    if (app.globalData.isLoggedIn) {
      this.loadHistory();
    }
  },

  // 加载历史记录
  loadHistory: async function () {
    this.setData({ loading: true });

    try {
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
      
      // 如果云函数失败，显示模拟数据
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

  // 返回
  onBack: function () {
    // 在tabBar页面，返回无效
    console.log('onBack');
  },

  // 下拉刷新
  onPullDownRefresh: function () {
    this.loadHistory().then(() => {
      wx.stopPullDownRefresh();
    });
  }
});