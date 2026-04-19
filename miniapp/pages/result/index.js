const api = require('../../utils/api');
const auth = require('../../utils/auth');
const { RECENT_PRACTICE_LIMIT } = require('../../config');
const { buildGrowthInsights, buildResultFollowUp } = require('../../utils/practice');
const { FORMAL_SUPPORT_TEXT, getScriptMeta } = require('../../utils/script');

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
  if (level === 'good') return '优';
  if (level === 'bad') return '待提升';
  return '良';
}

function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--';
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function normalizeRubricCards(rawItems = []) {
  return (rawItems || [])
    .filter((item) => item && item.key)
    .map((item) => ({
      key: item.key,
      label: item.label || item.key,
      score: Math.round(Number(item.score || 0)),
      focus: item.focus || '',
      evidenceSummary: item.evidence_summary || '',
      basisCodes: item.basis_codes || [],
      basisLabels: item.basis_labels || [],
      practiceTemplates: item.practice_templates || [],
    }));
}

function buildRubricSummary(rawResult, cards = []) {
  if (rawResult.is_legacy_standard) {
    return '这条记录仍沿用旧版评测标准，建议重新生成新版正式 rubric 记录。';
  }
  if (!cards.length) {
    return '当前记录还没有生成正式 rubric 结果。';
  }

  const summary = rawResult.rubric_summary || {};
  const best = summary.best || [...cards].sort((left, right) => right.score - left.score)[0];
  const weakest = summary.weakest || [...cards].sort((left, right) => left.score - right.score)[0];
  return `当前强项：${best.label} ${best.score} 分；优先提升：${weakest.label} ${weakest.score} 分。`;
}

function buildEvidenceCards(rawResult, cards = []) {
  if (rawResult.is_legacy_standard || !cards.length) {
    return [];
  }

  const referenceMap = {};
  (rawResult.rubric_source_refs || []).forEach((item) => {
    if (item && item.code) {
      referenceMap[item.code] = item;
    }
  });

  return cards.map((item) => {
    const sources = (item.basisCodes || [])
      .map((code) => referenceMap[code])
      .filter(Boolean);
    const sourceTitles = sources.map((source) => source.title);
    const observationPoints = sources.length
      ? sources.map((source) => source.organization || source.code)
      : item.basisCodes;
    const practiceHint = item.practiceTemplates && item.practiceTemplates.length
      ? item.practiceTemplates[0]
      : '继续按当前标准项补一轮，生成下一条可对比记录。';

    return {
      key: item.key,
      label: item.label,
      scoreText: `${item.score}`,
      core_question: item.focus || `${item.label} 对应的是当前正式评审标准中的重点观察项。`,
      observation_points: observationPoints,
      featureText: sourceTitles.join(' / ') || (item.basisLabels || []).join(' / '),
      practice_tip: `${item.evidenceSummary || ''}${item.evidenceSummary ? '；' : ''}${practiceHint}`,
    };
  });
}

function buildMetrics(result) {
  return [
    {
      title: '识别结果',
      value: result.characterLabel,
      note: `OCR 置信度 ${result.ocrText}`,
    },
    {
      title: '书体',
      value: result.scriptLabel,
      note: result.scriptStatusText,
    },
    {
      title: '主分等级',
      value: result.qualityLabel,
      note: `质量置信度 ${result.qualityText}`,
    },
    {
      title: '评审标准',
      value: result.isLegacyStandard ? '旧版标准' : result.rubricLabel,
      note: result.isLegacyStandard
        ? '这条记录生成于新版来源化标准接入前，仅保留为历史对照。'
        : '当前只上屏正式五维标准，不展示试运行总分。',
    },
  ];
}

function normalizeReviewSummary(summary = null, reviews = []) {
  const payload = summary || {};
  const latestReview = payload.latest_review || (reviews && reviews[0]) || null;
  const reviewCount = Number(payload.review_count || 0);

  return {
    reviewCount,
    validationStatus: payload.validation_status || 'pending_review',
    agreementText:
      payload.agreement === null || payload.agreement === undefined
        ? '待人工对照'
        : payload.agreement
          ? '与人工等级一致'
          : '与人工等级存在差异',
    averageReviewScoreText:
      payload.average_review_score === null || payload.average_review_score === undefined
        ? '--'
        : `${Math.round(Number(payload.average_review_score) * 10) / 10}`,
    scoreGapText:
      payload.score_gap === null || payload.score_gap === undefined
        ? '--'
        : `${Math.round(Number(payload.score_gap) * 10) / 10}`,
    latestReviewer: latestReview ? latestReview.reviewer_name || '教师复评' : '待教师复评',
    latestRole: latestReview ? latestReview.reviewer_role || '人工校核' : '等待复评',
    latestNote: latestReview
      ? latestReview.notes || '本次复评未填写附加说明。'
      : '当前结果还没有进入教师 / 专家复评。',
  };
}

const EMPTY_GROWTH = buildGrowthInsights([]);
const EMPTY_FOLLOW_UP = buildResultFollowUp({}, EMPTY_GROWTH);

Page({
  data: {
    loading: true,
    result: null,
    metrics: [],
    dimensionCards: [],
    dimensionSummary: '',
    basisCards: [],
    practiceProfile: null,
    reviewSummary: null,
    growthSummary: EMPTY_GROWTH.growthSummary,
    resultFollowUp: EMPTY_FOLLOW_UP,
    practicePreview: [],
    supportScopeText: FORMAL_SUPPORT_TEXT,
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
      const [data, historyPayload] = await Promise.all([
        api.getResultDetail(this.resultId),
        api.getHistory({ sort: 'latest', limit: RECENT_PRACTICE_LIMIT }).catch(() => ({ items: [] })),
      ]);
      const rawResult = data.result || {};
      const palette = getScorePalette(rawResult.total_score || 0);
      const rubricCards = normalizeRubricCards(rawResult.rubric_items);
      const practiceProfile = rawResult.practice_profile || null;
      const growthInsights = buildGrowthInsights((historyPayload && historyPayload.items) || []);
      const reviewSummary = normalizeReviewSummary(rawResult.expert_review_summary, rawResult.expert_reviews);
      const scriptMeta = getScriptMeta(rawResult);

      const result = {
        ...rawResult,
        ...palette,
        ...scriptMeta,
        qualityLabel: rawResult.quality_label || getQualityLabel(rawResult.quality_level),
        characterLabel: rawResult.character_name || '未识别',
        deviceLabel: rawResult.device_name || 'InkPi 设备',
        ocrText: formatConfidence(rawResult.ocr_confidence),
        qualityText: formatConfidence(rawResult.quality_confidence),
        isLegacyStandard: !!rawResult.is_legacy_standard,
        rubricLabel:
          rawResult.current_rubric_label ||
          rawResult.rubric_label ||
          rawResult.rubric_family ||
          '来源化正式标准',
        practiceProfile,
      };

      this.setData({
        result,
        metrics: buildMetrics(result),
        dimensionCards: rubricCards,
        dimensionSummary: buildRubricSummary(rawResult, rubricCards),
        basisCards: buildEvidenceCards(rawResult, rubricCards),
        practiceProfile,
        reviewSummary,
        growthSummary: growthInsights.growthSummary,
        resultFollowUp: buildResultFollowUp(rawResult, growthInsights),
        practicePreview: growthInsights.recommendations.slice(0, 2),
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

  goPractice() {
    wx.navigateTo({ url: '/pages/practice/index?source=result' });
  },
});
