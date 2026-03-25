const { API_BASE_URL } = require('../config');
const { getToken } = require('./auth');

function request(path, options = {}) {
  const token = getToken();
  const headers = Object.assign({}, options.header || {});

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: options.timeout || 10000,
      header: headers,
      success(res) {
        const data = res.data || {};
        if (res.statusCode >= 200 && res.statusCode < 300 && data.ok) {
          resolve(data);
          return;
        }
        reject(new Error(data.error || `HTTP_${res.statusCode}`));
      },
      fail(err) {
        reject(new Error(err.errMsg || 'NETWORK_ERROR'));
      },
    });
  });
}

function login(username, password) {
  return request('/api/auth/login', {
    method: 'POST',
    header: { 'Content-Type': 'application/json' },
    data: { username, password },
  });
}

function getHistory(limit = 30) {
  return request(`/api/results?limit=${limit}`);
}

function getResultDetail(id) {
  return request(`/api/results/${id}`);
}

module.exports = {
  login,
  getHistory,
  getResultDetail,
};
