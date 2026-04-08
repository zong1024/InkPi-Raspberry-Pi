const api = require('../../utils/api');
const auth = require('../../utils/auth');

const DIMENSION_LABELS = {
  structure: '结构',
  stroke: '笔画',
  integrity: '完整',
  stability: '稳定',
};

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
  if (level === 'good') return '甲';
  if (level === 'bad') return '丙';
  return '乙';
}

function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function buildDimensionCards(dimensionScores = null) {
  if (!dimensionScores) {
    return [];
  }

  return Object.entries(DIMENSION_LABELS)
    .filter(([key]) => dimensionScores[key] !== undefined && dimensionScores[key] !== null)
    .map(([key, label]) => ({
      key,
      label,
      score: Number(dimensionScores[key]),
    }));
}

function buildDimensionSummary(cards = []) {
  if (!cards.length) {
    return '老记录暂时没有四维解释分。';
  }
  const strongest = [...cards].sort((left, right) => right.score - left.score)[0];
  const weakest = [...cards].sort((left, right) => left.score - right.score)[0];
  return `当前强项：${strongest.label} ${strongest.score} 分；优先提升：${weakest.label} ${weakest.score} 分。`;
}

function normalizeBasisCards(cards = []) {
  return cards.map((item) => ({
    ...item,
    scoreText: item.score === null || item.score === undefined ? '--' : `${Math.round(Number(item.score))}`,
    featureText: Array.isArray(item.feature_mapping) ? item.feature_mapping.join(' / ') : '',
  }));
}

function buildMetrics(result) {
  return [
    {
      title: '识别结果',
      value: result.characterLabel,
      note: `OCR 置信度 ${result.ocrText}`,
    },
    {
      title: '主分等级',
      value: result.qualityLabel,
      note: `质量置信度 ${result.qualityText}`,
    },
    {
      title: '当前定位',
      value: result.practiceProfile ? result.practiceProfile.stage_label : '辅助评测',
      note: result.practiceProfile
        ? result.practiceProfile.scope_note
        : '当前系统面向楷书单字辅助评测，不替代教师终评。',
    },
  ];
}

Page({
  data: {
    loading: true,
    result: null,
    metrics: [],
    dimensionCards: [],
    dimensionSummary: '',
    basisCards: [],
    practiceProfile: null,
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
      const dimensionCards = buildDimensionCards(rawResult.dimension_scores);
      const practiceProfile = rawResult.practice_profile || null;

      const result = {
        ...rawResult,
        ...palette,
        qualityLabel: rawResult.quality_label || getQualityLabel(rawResult.quality_level),
        characterLabel: rawResult.character_name || '未识别',
        deviceLabel: rawResult.device_name || 'InkPi 设备',
        ocrText: formatConfidence(rawResult.ocr_confidence),
        qualityText: formatConfidence(rawResult.quality_confidence),
        practiceProfile,
      };

      this.setData({
        result,
        metrics: buildMetrics(result),
        dimensionCards,
        dimensionSummary: buildDimensionSummary(dimensionCards),
        basisCards: normalizeBasisCards(rawResult.dimension_basis || []),
        practiceProfile,
      });
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
        content: `确认删除“${result.characterLabel || '未识别'}”这条记录吗？`,
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
        if (getCurrentPages().length > 1) {
          wx.navigateBack();
        } else {
          wx.reLaunch({ url: '/pages/history/index' });
        }
      }, 300);
    } catch (error) {
      wx.showToast({ title: '删除失败', icon: 'none' });
      this.setData({ deleting: false });
    }
  },

  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.reLaunch({ url: '/pages/history/index' });
  },

  goStats() {
    wx.navigateTo({ url: '/pages/stats/index' });
  },
});
