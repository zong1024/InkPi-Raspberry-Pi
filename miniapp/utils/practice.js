const {
  DEFAULT_WEEKLY_GOAL,
  PRACTICE_RECOMMENDATION_COUNT,
  PRACTICE_TARGET_SCORE,
  RECENT_PRACTICE_LIMIT,
  STABLE_PRACTICE_TARGET,
  STABLE_SCORE_LINE,
} = require('../config');

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
  const date = value instanceof Date ? value : new Date(`${value}`.replace(/-/g, '/'));
  return Number.isNaN(date.getTime()) ? null : date;
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

function normalizeRubricItems(rawItems = []) {
  return (rawItems || [])
    .filter((item) => item && item.key)
    .map((item) => ({
      key: item.key,
      label: item.label || item.key,
      score: toNumber(item.score) || 0,
      tip: item.evidence_summary || '',
      actions: item.practice_templates || [],
    }));
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
        script: item.script || 'regular',
        scriptLabel: item.script_label || (item.script === 'running' ? '行书' : '楷书'),
        rubricItems: normalizeRubricItems(item.rubric_items || item.rubricItems || []),
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
      statusText: '今天重新开练，新的连续天数就会开始累积。',
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
      : `昨天练过，今天再练一次就能续上 ${streakDays} 天连续练习。`,
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
  const latestRecord = records[0] || null;
  const remainingDays = Math.max(weeklyGoalDays - weekActiveDays, 0);

  let message = '先完成一条练习记录，系统会开始生成你的成长节奏。';
  if (weekActiveDays >= weeklyGoalDays) {
    message = `本周目标已完成，本周已有 ${weekRecords.length} 条记录，接下来重点把弱项稳定下来。`;
  } else if (streakInfo.practicedToday) {
    message = `今天已经打卡，本周再完成 ${remainingDays} 天就能达成周目标。`;
  } else if (streakInfo.practicedYesterday) {
    message = `今天补练一次就能续上连续练习，同时把本周目标推进到 ${weekActiveDays + 1}/${weeklyGoalDays} 天。`;
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

function buildRubricInsights(records = []) {
  const rubricBuckets = {};
  records.forEach((item) => {
    (item.rubricItems || []).forEach((rubric) => {
      if (!rubricBuckets[rubric.key]) {
        rubricBuckets[rubric.key] = {
          key: rubric.key,
          label: rubric.label,
          scores: [],
          actions: rubric.actions || [],
          tip: rubric.tip || '',
        };
      }
      rubricBuckets[rubric.key].scores.push(rubric.score);
      if (!rubricBuckets[rubric.key].tip && rubric.tip) {
        rubricBuckets[rubric.key].tip = rubric.tip;
      }
      if ((!rubricBuckets[rubric.key].actions || !rubricBuckets[rubric.key].actions.length) && rubric.actions) {
        rubricBuckets[rubric.key].actions = rubric.actions;
      }
    });
  });

  const rubrics = Object.values(rubricBuckets)
    .map((item) => {
      const averageScore = average(item.scores);
      return {
        key: item.key,
        label: item.label,
        count: item.scores.length,
        averageScore,
        averageText: formatScore(averageScore),
        gapText:
          averageScore === null
            ? '--'
            : `${Math.max(PRACTICE_TARGET_SCORE - averageScore, 0).toFixed(1)} 分`,
        actions: item.actions || [],
        note: item.tip || '',
      };
    })
    .filter((item) => item.count > 0)
    .sort((left, right) => left.averageScore - right.averageScore);

  if (!rubrics.length) {
    return {
      rubrics: [],
      focusDimension: null,
      strongDimension: null,
    };
  }

  const focusDimension = Object.assign({}, rubrics[0], {
    note: rubrics[0].note || `${rubrics[0].label} 是当前最值得优先补强的标准项。`,
  });
  const strongest = rubrics[rubrics.length - 1];
  const strongDimension = Object.assign({}, strongest, {
    note: strongest.note || `${strongest.label} 是当前最稳的标准项，训练时尽量保留下来。`,
  });

  return {
    rubrics,
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

  return Object.values(grouped)
    .map((item) => {
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
              ? `最近一次比最好成绩低 ${formatScore(bestGap)} 分，适合马上回练。`
              : `已经练过 ${item.count} 次，再补一轮更容易把表现写稳。`
            : `最近一次得到 ${formatScore(item.latestScore)}，趁记忆还新再写一轮更有效。`,
        badgeText: item.count > 1 ? `${item.count} 次记录` : '最新建议',
        latestDate: item.latestDate,
      };
    })
    .sort((left, right) => left.averageScore - right.averageScore || right.count - left.count)
    .slice(0, count);
}

function buildMilestoneCards(growthSummary, rubricInsights) {
  const focusDimension = rubricInsights.focusDimension;
  return [
    {
      key: 'streak',
      label: '连续练习',
      value: growthSummary.streakText,
      note: growthSummary.practicedToday ? '今天已打卡' : '今天继续补一轮',
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
      note: focusDimension ? `当前优先项 ${focusDimension.label}` : '继续积累新标准记录',
    },
  ];
}

function buildSessionPlan(growthSummary, rubricInsights, recommendations = []) {
  const focusDimension = rubricInsights.focusDimension;
  const practiceCharacters = recommendations.slice(0, 2).map((item) => item.character);
  const charactersText = practiceCharacters.length ? practiceCharacters.join('、') : '最近的目标字';
  const focusLabel = focusDimension ? focusDimension.label : '正式标准项';

  return {
    title: growthSummary.practicedToday ? '下一轮练习建议' : '今天的练习建议',
    subtitle: focusDimension
      ? `先盯 ${focusLabel}，再看主分，训练效率会更高。`
      : '先完成一轮短练和一次复测，系统才有数据给出更准建议。',
    actions: [
      `热身 3 分钟：先写 1 轮 ${charactersText}，只关注 ${focusLabel}。`,
      '重点 5 分钟：每写完一张就自查 1 次，保留最接近目标的一张。',
      `收尾 2 分钟：再上传 1 条评测，看看 ${focusLabel} 是否更稳定。`,
    ],
    footer:
      growthSummary.weekActiveDays >= growthSummary.weeklyGoalDays
        ? '本周目标已经完成，下一步把高分表现稳定下来。'
        : `本周再完成 ${Math.max(growthSummary.weeklyGoalDays - growthSummary.weekActiveDays, 0)} 天，就能达成周目标。`,
  };
}

function buildGrowthInsights(items = [], options = {}) {
  const normalizedRecords = normalizeHistoryItems(items).slice(0, options.limit || RECENT_PRACTICE_LIMIT);
  const growthSummary = buildGrowthSummary(normalizedRecords, options);
  const dimensionInsights = buildRubricInsights(normalizedRecords);
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
    tip: profileSection.evidence_summary || profileSection.tip || '',
  };
}

function buildResultFollowUp(result = {}, growthInsights = {}) {
  const rubricItems = normalizeRubricItems(result.rubric_items || result.rubricItems || []);
  const sortedRubrics = [...rubricItems].sort((left, right) => left.score - right.score);
  const profile = result.practice_profile || result.practiceProfile || null;
  const defaultFocus = sortedRubrics.length ? sortedRubrics[0] : null;
  const defaultStrong = sortedRubrics.length ? sortedRubrics[sortedRubrics.length - 1] : null;
  const focusDimension = getProfileDimension(profile && profile.focus_dimension, defaultFocus);
  const strongDimension = getProfileDimension(profile && profile.best_dimension, defaultStrong);
  const growthSummary = growthInsights.growthSummary || buildGrowthInsights([]).growthSummary;
  const defaultActions = (defaultFocus && defaultFocus.actions) || [];
  const nextActions = (
    profile && Array.isArray(profile.next_actions) && profile.next_actions.length
      ? profile.next_actions
      : defaultActions
  ).slice(0, 3);

  let note = '继续保持节奏，下一次复测会更容易看到变化。';
  if (focusDimension) {
    note = `${focusDimension.label} 当前 ${formatScore(focusDimension.score)} 分，是这次最值得优先补强的部分。`;
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
  buildGrowthInsights,
  buildResultFollowUp,
  formatScore,
};
