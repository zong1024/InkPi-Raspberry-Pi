const {
  DEFAULT_WEEKLY_GOAL,
  PRACTICE_RECOMMENDATION_COUNT,
  PRACTICE_TARGET_SCORE,
  RECENT_PRACTICE_LIMIT,
  STABLE_PRACTICE_TARGET,
  STABLE_SCORE_LINE,
} = require('../config');

const DIMENSION_LABELS = {
  structure: '结构',
  stroke: '笔画',
  integrity: '完整',
  stability: '稳定',
};

const DIMENSION_ACTIONS = {
  structure: [
    '先看中宫和主笔位置，再下笔，别急着写满整格。',
    '一轮只练一个字的主结构，写完马上对照左右和上下比例。',
    '复测前先挑 1 张最顺手的样张，照着同样的字距再写一遍。',
  ],
  stroke: [
    '每轮只盯起笔、行笔、收笔三处，宁可慢一点也不要抖。',
    '横竖先求长度稳定，再追求粗细变化，避免一上来就追速度。',
    '复测前先空写 3 次主笔轨迹，让笔路先热起来。',
  ],
  integrity: [
    '先把字写完整，再追求漂亮，别让局部断掉整字节奏。',
    '每写完一轮就自查有没有缺笔、连笔过头或转折丢失。',
    '复测时优先保证收笔干净，减少“写到最后松掉”的情况。',
  ],
  stability: [
    '连续写 3 次同一个字，要求每次大小、倾斜和重心都接近。',
    '先固定书写节奏，再微调细节，避免一笔一笔临时起意。',
    '复测前把坐姿和纸张位置固定好，先稳住再冲分。',
  ],
};

function pad(value) {
  return `${value}`.padStart(2, '0');
}

function toNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }
  return Number(value);
}

function formatScore(value) {
  const numberValue = toNumber(value);
  if (numberValue === null) {
    return '--';
  }
  return `${Math.round(numberValue * 10) / 10}`;
}

function parseTimestamp(value) {
  if (!value) {
    return null;
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const text = `${value}`.trim();
  const matched = text.match(
    /(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?)?/
  );

  if (matched) {
    const [, year, month, day, hour = '0', minute = '0', second = '0'] = matched;
    const date = new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second)
    );
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const fallbackDate = new Date(text.replace(/-/g, '/'));
  return Number.isNaN(fallbackDate.getTime()) ? null : fallbackDate;
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date, offset) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + offset);
  return nextDate;
}

function getDateKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function getStartOfWeek(date) {
  const day = date.getDay() || 7;
  return addDays(startOfDay(date), 1 - day);
}

function formatShortDate(date) {
  if (!date) {
    return '暂无记录';
  }
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

function average(values) {
  const validValues = values.filter((item) => item !== null && item !== undefined);
  if (!validValues.length) {
    return null;
  }
  return validValues.reduce((sum, item) => sum + Number(item), 0) / validValues.length;
}

function normalizeHistoryItems(items = []) {
  return items
    .map((item, index) => {
      const date = parseTimestamp(item.timestamp || item.created_at || item.updated_at);
      return {
        id: item.id || `record-${index}`,
        raw: item,
        date,
        dateKey: date ? getDateKey(date) : '',
        timestampText: item.timestamp || item.created_at || '',
        totalScore: toNumber(item.total_score || item.totalScore) || 0,
        character: item.character_name || item.characterLabel || item.character || '未识别',
        device: item.device_name || item.deviceLabel || 'InkPi 设备',
        dimensionScores: item.dimension_scores || item.dimensionScores || null,
      };
    })
    .filter((item) => item.date)
    .sort((left, right) => right.date.getTime() - left.date.getTime());
}

function buildStreakInfo(records, now = new Date()) {
  const dayKeys = Array.from(new Set(records.map((item) => item.dateKey)));
  const dayKeySet = new Set(dayKeys);
  const today = startOfDay(now);
  const todayKey = getDateKey(today);
  const yesterdayKey = getDateKey(addDays(today, -1));
  const practicedToday = dayKeySet.has(todayKey);
  const practicedYesterday = dayKeySet.has(yesterdayKey);

  if (!practicedToday && !practicedYesterday) {
    return {
      practicedToday: false,
      practicedYesterday: false,
      streakDays: 0,
      streakText: '0 天',
      statusText: '今天重新开练，新的连续天数就会开始累计。',
    };
  }

  let cursor = practicedToday ? today : addDays(today, -1);
  let streakDays = 0;

  while (dayKeySet.has(getDateKey(cursor))) {
    streakDays += 1;
    cursor = addDays(cursor, -1);
  }

  return {
    practicedToday,
    practicedYesterday,
    streakDays,
    streakText: `${streakDays} 天`,
    statusText: practicedToday
      ? `今天已经完成练习，连续练习 ${streakDays} 天。`
      : `昨天练过，今天再练一次就能续上 ${streakDays} 天连练。`,
  };
}

function buildGrowthSummary(records = [], options = {}) {
  const now = options.now || new Date();
  const weeklyGoalDays = options.weeklyGoalDays || DEFAULT_WEEKLY_GOAL;
  const weekStart = getStartOfWeek(now);
  const weekEnd = addDays(weekStart, 7);
  const streakInfo = buildStreakInfo(records, now);
  const weekRecords = records.filter((item) => item.date >= weekStart && item.date < weekEnd);
  const weekActiveDays = new Set(weekRecords.map((item) => item.dateKey)).size;
  const stableUploads = weekRecords.filter((item) => item.totalScore >= STABLE_SCORE_LINE).length;
  const weekGoalPercent = Math.min(
    100,
    Math.round((weekActiveDays / Math.max(weeklyGoalDays, 1)) * 100)
  );
  const latestRecord = records[0] || null;
  const remainingDays = Math.max(weeklyGoalDays - weekActiveDays, 0);

  let message = '先完成一条练习记录，系统会开始生成你的成长节奏。';
  if (weekActiveDays >= weeklyGoalDays) {
    message = `本周目标已完成，本周已有 ${weekRecords.length} 条记录，接下来重点把高分表现稳定下来。`;
  } else if (streakInfo.practicedToday) {
    message = `今天已经打卡，本周再完成 ${remainingDays} 天就能达成周目标。`;
  } else if (streakInfo.practicedYesterday) {
    message = `今天补练一次就能续上连练，同时把本周目标推进到 ${weekActiveDays + 1}/${weeklyGoalDays} 天。`;
  } else if (weekRecords.length) {
    message = `最近已经有 ${weekRecords.length} 条记录，但连续性还没建立，建议今天先补一次短练。`;
  }

  return {
    practicedToday: streakInfo.practicedToday,
    practicedYesterday: streakInfo.practicedYesterday,
    streakDays: streakInfo.streakDays,
    streakText: streakInfo.streakText,
    statusText: streakInfo.statusText,
    weeklyGoalDays,
    weekActiveDays,
    weekRecords: weekRecords.length,
    weekGoalPercent,
    weekGoalText: `${weekActiveDays}/${weeklyGoalDays} 天`,
    stableUploads,
    stableTarget: STABLE_PRACTICE_TARGET,
    stableProgressText: `${stableUploads}/${STABLE_PRACTICE_TARGET} 条`,
    lastPracticeText: latestRecord
      ? `最近一次练习 ${formatShortDate(latestRecord.date)}`
      : '还没有练习记录',
    latestCharacterText: latestRecord ? latestRecord.character : '未开始',
    message,
  };
}

function buildDimensionInsights(records = []) {
  const dimensionBuckets = Object.keys(DIMENSION_LABELS).reduce((accumulator, key) => {
    accumulator[key] = [];
    return accumulator;
  }, {});

  records.forEach((item) => {
    if (!item.dimensionScores) {
      return;
    }

    Object.keys(DIMENSION_LABELS).forEach((key) => {
      const value = toNumber(item.dimensionScores[key]);
      if (value !== null) {
        dimensionBuckets[key].push(value);
      }
    });
  });

  const dimensions = Object.keys(DIMENSION_LABELS)
    .map((key) => {
      const scores = dimensionBuckets[key];
      const averageScore = average(scores);
      return {
        key,
        label: DIMENSION_LABELS[key],
        count: scores.length,
        averageScore,
        averageText: formatScore(averageScore),
        gapText:
          averageScore === null
            ? '--'
            : `${Math.max(PRACTICE_TARGET_SCORE - averageScore, 0).toFixed(1)} 分`,
        actions: DIMENSION_ACTIONS[key] || [],
      };
    })
    .filter((item) => item.count > 0)
    .sort((left, right) => left.averageScore - right.averageScore);

  if (!dimensions.length) {
    return {
      dimensions: [],
      focusDimension: null,
      strongDimension: null,
    };
  }

  const focusDimension = Object.assign({}, dimensions[0], {
    note: `最近 ${dimensions[0].count} 条有维度分的记录里，${dimensions[0].label}均值 ${dimensions[0].averageText}，最值得优先补强。`,
  });
  const strongest = dimensions[dimensions.length - 1];
  const strongDimension = Object.assign({}, strongest, {
    note: `${strongest.label}目前是最稳定的一项，练新动作时尽量把它保留下来。`,
  });

  return {
    dimensions,
    focusDimension,
    strongDimension,
  };
}

function buildCharacterRecommendations(records = [], count = PRACTICE_RECOMMENDATION_COUNT) {
  const grouped = {};

  records.forEach((item) => {
    if (!item.character || item.character === '未识别') {
      return;
    }

    if (!grouped[item.character]) {
      grouped[item.character] = {
        character: item.character,
        count: 0,
        totalScore: 0,
        bestScore: item.totalScore,
        latestScore: item.totalScore,
        latestDate: item.date,
      };
    }

    const bucket = grouped[item.character];
    bucket.count += 1;
    bucket.totalScore += item.totalScore;
    bucket.bestScore = Math.max(bucket.bestScore, item.totalScore);

    if (!bucket.latestDate || item.date.getTime() > bucket.latestDate.getTime()) {
      bucket.latestDate = item.date;
      bucket.latestScore = item.totalScore;
    }
  });

  const groups = Object.keys(grouped).map((key) => {
    const item = grouped[key];
    const averageScore = item.totalScore / item.count;
    const bestGap = Math.max(item.bestScore - item.latestScore, 0);

    return {
      character: item.character,
      count: item.count,
      averageScore,
      averageText: formatScore(averageScore),
      latestScoreText: formatScore(item.latestScore),
      bestScoreText: formatScore(item.bestScore),
      reason:
        item.count > 1
          ? bestGap >= 4
            ? `最近一次比最佳成绩低 ${formatScore(bestGap)} 分，适合马上回练。`
            : `已经练过 ${item.count} 次，再补一轮更容易把分数写稳。`
          : `最近一次得分 ${formatScore(item.latestScore)}，趁记忆还新再写一轮更有效。`,
      badgeText: item.count > 1 ? `${item.count} 次记录` : '最新建议',
      latestDate: item.latestDate,
    };
  });

  const repeated = groups
    .filter((item) => item.count > 1)
    .sort((left, right) => left.averageScore - right.averageScore || right.count - left.count);
  const recentSingles = groups
    .filter((item) => item.count === 1)
    .sort(
      (left, right) =>
        left.averageScore - right.averageScore ||
        right.latestDate.getTime() - left.latestDate.getTime()
    );

  return repeated.concat(recentSingles).slice(0, count);
}

function buildMilestoneCards(growthSummary, dimensionInsights) {
  const focusDimension = dimensionInsights.focusDimension;

  return [
    {
      key: 'streak',
      label: '连续练习',
      value: growthSummary.streakText,
      note: growthSummary.practicedToday
        ? '今天已打卡'
        : growthSummary.practicedYesterday
          ? '今天补一次可续上'
          : '今天开始重新累计',
    },
    {
      key: 'weekly-goal',
      label: '本周目标',
      value: growthSummary.weekGoalText,
      note: `目标 ${growthSummary.weeklyGoalDays} 天`,
    },
    {
      key: 'stable',
      label: '稳定 80+',
      value: growthSummary.stableProgressText,
      note: focusDimension ? `当前优先补 ${focusDimension.label}` : '继续累积练习样本',
    },
  ];
}

function buildSessionPlan(growthSummary, dimensionInsights, recommendations = []) {
  const focusDimension = dimensionInsights.focusDimension;
  const practiceCharacters = recommendations.slice(0, 2).map((item) => item.character);
  const charactersText = practiceCharacters.length ? practiceCharacters.join('、') : '最近的目标字';
  const focusLabel = focusDimension ? focusDimension.label : '主结构';

  return {
    title: growthSummary.practicedToday ? '下一轮练习建议' : '今天的练习建议',
    subtitle: focusDimension
      ? `先盯 ${focusLabel}，再去追总分，练习效率会更高。`
      : '先完成一轮短练和一次复测，系统才有数据给你更准的建议。',
    actions: [
      `热身 3 分钟：先写 1 轮 ${charactersText}，只关注 ${focusLabel}。`,
      '重点 5 分钟：每写完一张就自查 1 次，保留最接近目标的一张。',
      `收尾 2 分钟：再上传 1 条评测，看看 ${focusLabel}是否更稳定。`,
    ],
    footer:
      growthSummary.weekActiveDays >= growthSummary.weeklyGoalDays
        ? '本周目标已经完成，下一步把高分表现稳定下来。'
        : `本周再完成 ${Math.max(growthSummary.weeklyGoalDays - growthSummary.weekActiveDays, 0)} 天，就能达成周目标。`,
  };
}

function buildGrowthInsights(items = [], options = {}) {
  const normalizedRecords = normalizeHistoryItems(items).slice(
    0,
    options.limit || RECENT_PRACTICE_LIMIT
  );
  const growthSummary = buildGrowthSummary(normalizedRecords, options);
  const dimensionInsights = buildDimensionInsights(normalizedRecords);
  const recommendations = buildCharacterRecommendations(
    normalizedRecords,
    options.recommendationCount || PRACTICE_RECOMMENDATION_COUNT
  );

  return {
    records: normalizedRecords,
    hasData: normalizedRecords.length > 0,
    growthSummary,
    dimensionInsights,
    recommendations,
    milestoneCards: buildMilestoneCards(growthSummary, dimensionInsights),
    sessionPlan: buildSessionPlan(growthSummary, dimensionInsights, recommendations),
  };
}

function getProfileDimension(profileSection, fallback) {
  if (!profileSection) {
    return fallback || null;
  }

  return {
    key: profileSection.key || (fallback && fallback.key) || '',
    label: profileSection.label || (fallback && fallback.label) || '重点项',
    score:
      toNumber(profileSection.score) !== null
        ? Number(profileSection.score)
        : (fallback && fallback.score) || 0,
    tip: profileSection.tip || '',
  };
}

function buildResultFollowUp(result = {}, growthInsights = {}) {
  const dimensionScores = result.dimension_scores || result.dimensionScores || {};
  const resultDimensions = Object.keys(DIMENSION_LABELS)
    .filter((key) => dimensionScores[key] !== undefined && dimensionScores[key] !== null)
    .map((key) => ({
      key,
      label: DIMENSION_LABELS[key],
      score: Number(dimensionScores[key]),
    }))
    .sort((left, right) => left.score - right.score);
  const profile = result.practice_profile || result.practiceProfile || null;
  const defaultFocus = resultDimensions.length ? resultDimensions[0] : null;
  const defaultStrong = resultDimensions.length ? resultDimensions[resultDimensions.length - 1] : null;
  const focusDimension = getProfileDimension(profile && profile.focus_dimension, defaultFocus);
  const strongDimension = getProfileDimension(profile && profile.best_dimension, defaultStrong);
  const growthSummary = growthInsights.growthSummary || buildGrowthInsights([]).growthSummary;
  const defaultActions =
    (focusDimension && DIMENSION_ACTIONS[focusDimension.key]) || DIMENSION_ACTIONS.structure || [];
  const nextActions = (
    profile && Array.isArray(profile.next_actions) && profile.next_actions.length
      ? profile.next_actions
      : defaultActions
  ).slice(0, 3);

  let note = '继续保持节奏，下一次复测会更容易看到变化。';
  if (focusDimension) {
    note = `${focusDimension.label}当前 ${formatScore(focusDimension.score)} 分，是这次最值得优先补强的部分。`;
  }

  return {
    title: focusDimension ? `下一次先练 ${focusDimension.label}` : '继续完成下一轮练习',
    note,
    focusDimension,
    strongDimension,
    nextActions,
    weeklyHint: growthSummary.message,
    progressChips: [
      `连续练习 ${growthSummary.streakText}`,
      `本周目标 ${growthSummary.weekGoalText}`,
      `稳定 80+ ${growthSummary.stableProgressText}`,
    ],
  };
}

module.exports = {
  DIMENSION_LABELS,
  buildGrowthInsights,
  buildResultFollowUp,
  formatScore,
};
