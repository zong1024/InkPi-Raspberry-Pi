// app.js
App({
  onLaunch: function () {
    // 初始化云开发
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
    } else {
      wx.cloud.init({
        env: 'inkpi-cloud', // 云开发环境ID，需要替换为您自己的
        traceUser: true,
      });
    }

    // 检查登录状态
    this.checkLoginStatus();
  },

  // 检查登录状态
  checkLoginStatus: function () {
    const userInfo = wx.getStorageSync('userInfo');
    if (userInfo) {
      this.globalData.userInfo = userInfo;
      this.globalData.isLoggedIn = true;
    }
  },

  // 登录方法
  login: function () {
    return new Promise((resolve, reject) => {
      wx.getUserProfile({
        desc: '用于展示用户信息',
        success: (res) => {
          const userInfo = res.userInfo;
          this.globalData.userInfo = userInfo;
          this.globalData.isLoggedIn = true;
          wx.setStorageSync('userInfo', userInfo);
          
          // 调用云函数登录
          wx.cloud.callFunction({
            name: 'login',
            data: {
              userInfo: userInfo
            }
          }).then(result => {
            this.globalData.openid = result.result.openid;
            resolve(userInfo);
          }).catch(err => {
            console.error('云函数登录失败', err);
            resolve(userInfo); // 即使云函数失败也返回用户信息
          });
        },
        fail: (err) => {
          reject(err);
        }
      });
    });
  },

  globalData: {
    userInfo: null,
    isLoggedIn: false,
    openid: null
  }
});