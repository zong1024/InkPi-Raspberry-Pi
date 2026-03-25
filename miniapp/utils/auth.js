const TOKEN_KEY = 'inkpi_token';
const USER_KEY = 'inkpi_user';

function saveSession(token, user) {
  wx.setStorageSync(TOKEN_KEY, token);
  wx.setStorageSync(USER_KEY, user);
}

function clearSession() {
  wx.removeStorageSync(TOKEN_KEY);
  wx.removeStorageSync(USER_KEY);
}

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function getUser() {
  return wx.getStorageSync(USER_KEY) || null;
}

module.exports = {
  saveSession,
  clearSession,
  getToken,
  getUser,
};
