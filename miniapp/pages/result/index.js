const api = require('../../utils/api');
const auth = require('../../utils/auth');

function getScorePalette(score) {
  if (score >= 85) {
    return {
      scoreColor: '#3f8451',
      scoreSoft: 'rgba(224, 241, 226, 0.96)',
    };
  }
  if (score >= 70) {
    return {
      scoreColor: '#ab6d2f',
      scoreSoft: 'rgba(247, 232, 208, 0.96)',
    };
  }
  return {
    scoreColor: '#b34b3e',
    scoreSoft: 'rgba(252, 227, 221, 0.96)',
  };
}

function getGrade(score) {
  if (score >= 90) return '优秀';
  if (score >= 80) return '良好';
  if (score >= 70) return '稳定';
  if (score >= 60) return '继续练习';
  return '需强化';
}

function dimensionNote(name, value) {
  if (value >= 85) return `${name}表现稳定，可以继续保持。`;
  if (value >= 70) return `${name}整体不错，仍有继续优化空间。`;
  return `${name}偏弱，建议把这一项作为下一轮重点练习。`;
}

function dimensionColor(value) {
  if (value >= 85) return '#4f9d61';
  if (value >= 70) return '#b77a39';
  return '#c25b49';
}

Page({
  data: {
    loading: true,
    result: null,
    dimensions: [],
    error: '',
  },

  onLoad(options) {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/index' });
      return;
    }
    this.resultId = options.id;
    this.loadDetail();
  },

  onPullDownRefresh() {
    this.loadDetail().finally(() => wx.stopPullDownRefresh());
  },

  async loadDetail() {
    this.setData({ loading: true, error: '' });
    try {
      const data = await api.getResultDetail(this.resultId);
      const rawResult = data.result || {};
      const palette = getScorePalette(rawResult.total_score || 0);
      const order = ['结构', '笔画', '平衡', '韵律'];
      const detailScores = rawResult.detail_scores || {};

      const dimensions = order
        .filter((name) => Object.prototype.hasOwnProperty.call(detailScores, name))
        .map((name) => ({
          name,
          value: detailScores[name],
          color: dimensionColor(detailScores[name]),
          note: dimensionNote(name, detailScores[name]),
        }));

      const result = {
        ...rawResult,
        ...palette,
        grade: getGrade(rawResult.total_score || 0),
        characterLabel: rawResult.character_name || '未识别',
        styleLabel: rawResult.style || '未分类',
        deviceLabel: rawResult.device_name || 'InkPi 树莓派',
      };

      this.setData({ result, dimensions });
    } catch (error) {
      this.setData({ error: '加载详情失败，请返回历史页后重试。' });
    } finally {
      this.setData({ loading: false });
    }
  },
});
