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

function getQualityLabel(level) {
  if (level === 'good') return '好';
  if (level === 'bad') return '坏';
  return '中';
}

function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 100)}%`;
}

Page({
  data: {
    loading: true,
    result: null,
    metrics: [],
    error: '',
    deleting: false,
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

      const result = {
        ...rawResult,
        ...palette,
        qualityLabel: rawResult.quality_label || getQualityLabel(rawResult.quality_level),
        characterLabel: rawResult.character_name || '未识别',
        deviceLabel: rawResult.device_name || 'InkPi 树莓派',
        ocrText: formatConfidence(rawResult.ocr_confidence),
        qualityText: formatConfidence(rawResult.quality_confidence),
      };

      const metrics = [
        {
          title: '自动识别',
          value: result.characterLabel,
          note: `OCR 置信度 ${result.ocrText}`,
        },
        {
          title: '质量评级',
          value: result.qualityLabel,
          note: `模型置信度 ${result.qualityText}`,
        },
        {
          title: '单链路',
          value: 'OCR + ONNX',
          note: '当前版本固定使用自动 OCR 与 ONNX 评分模型。',
        },
      ];

      this.setData({ result, metrics });
    } catch (error) {
      this.setData({ error: '加载详情失败，请返回历史页后重试。' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async deleteCurrent() {
    if (!this.resultId) {
      return;
    }

    const result = this.data.result || {};
    const modal = await new Promise((resolve) => {
      wx.showModal({
        title: '删除记录',
        content: `确认删除「${result.characterLabel || '未识别'}」这条记录吗？`,
        confirmColor: '#b34b3e',
        success: resolve,
        fail: () => resolve({ confirm: false }),
      });
    });

    if (!modal.confirm) {
      return;
    }

    this.setData({ deleting: true });
    try {
      await api.deleteHistory(this.resultId);
      wx.showToast({ title: '已删除', icon: 'success' });
      setTimeout(() => {
        wx.navigateBack();
      }, 300);
    } catch (error) {
      wx.showToast({ title: '删除失败', icon: 'none' });
      this.setData({ deleting: false });
    }
  },

  goBack() {
    wx.navigateBack();
  },
});
