const FORMAL_SUPPORT_TEXT = '正式支持楷书、行书，其他书体暂不支持';
const FORMAL_SUPPORT_SHORT = '楷书 + 行书正式支持';
const UNSUPPORTED_SCOPE_TEXT = '其他书体暂不支持';

const SCRIPT_OPTIONS = ['全部书体', '楷书', '行书', '其他/未标注'];
const SCRIPT_VALUES = ['all', 'regular', 'running', 'unsupported'];

const SCRIPT_LABELS = {
  regular: '楷书',
  running: '行书',
  unsupported: '其他/未标注',
  unknown: '未标注',
};

const SCRIPT_FIELD_CANDIDATES = [
  'script',
  'script_name',
  'script_label',
  'script_type',
  'calligraphy_script',
  'character_script',
  'font_script',
  'font_style',
  'style_script',
];

function normalizeScriptKey(value) {
  if (value === null || value === undefined) {
    return '';
  }

  const raw = String(value).trim();
  if (!raw) {
    return '';
  }

  const normalized = raw.toLowerCase().replace(/[\s-]+/g, '_');

  if (
    raw === '楷书' ||
    raw === '楷書' ||
    raw === '楷体' ||
    raw === '楷體' ||
    normalized === 'regular' ||
    normalized === 'regular_script' ||
    normalized === 'kaishu' ||
    normalized === 'kai'
  ) {
    return 'regular';
  }

  if (
    raw === '行书' ||
    raw === '行書' ||
    normalized === 'running' ||
    normalized === 'running_script' ||
    normalized === 'xingshu' ||
    normalized === 'xing'
  ) {
    return 'running';
  }

  return 'unsupported';
}

function pickScriptValue(source = {}) {
  for (let index = 0; index < SCRIPT_FIELD_CANDIDATES.length; index += 1) {
    const field = SCRIPT_FIELD_CANDIDATES[index];
    const value = source[field];
    if (value !== null && value !== undefined && String(value).trim()) {
      return value;
    }
  }
  return '';
}

function getScriptLabel(scriptKey, rawValue = '') {
  if (scriptKey === 'regular' || scriptKey === 'running') {
    return SCRIPT_LABELS[scriptKey];
  }

  const raw = String(rawValue || '').trim();
  if (!raw) {
    return SCRIPT_LABELS.unknown;
  }
  return raw;
}

function getScriptMeta(source = {}) {
  const rawValue = pickScriptValue(source);
  const scriptKey = normalizeScriptKey(rawValue);
  const scriptLabel = getScriptLabel(scriptKey, rawValue);
  const scriptSupported = scriptKey === 'regular' || scriptKey === 'running';

  let scriptStatusText = '书体未标注，正式支持范围为楷书和行书';
  if (scriptKey === 'regular') {
    scriptStatusText = '楷书已正式支持';
  } else if (scriptKey === 'running') {
    scriptStatusText = '行书已正式支持';
  } else if (scriptLabel !== SCRIPT_LABELS.unknown) {
    scriptStatusText = `${scriptLabel}暂不支持`;
  }

  return {
    scriptKey: scriptSupported ? scriptKey : 'unsupported',
    scriptLabel,
    scriptBadgeText: `书体 ${scriptLabel}`,
    scriptStatusText,
    scriptSupported,
  };
}

function matchesScriptFilter(source = {}, scriptValue = 'all') {
  if (!scriptValue || scriptValue === 'all') {
    return true;
  }

  const { scriptKey } = getScriptMeta(source);
  if (scriptValue === 'unsupported') {
    return scriptKey !== 'regular' && scriptKey !== 'running';
  }
  return scriptKey === scriptValue;
}

function filterResultsByScript(items = [], scriptValue = 'all') {
  if (!Array.isArray(items) || scriptValue === 'all') {
    return Array.isArray(items) ? items : [];
  }
  return items.filter((item) => matchesScriptFilter(item, scriptValue));
}

module.exports = {
  FORMAL_SUPPORT_TEXT,
  FORMAL_SUPPORT_SHORT,
  UNSUPPORTED_SCOPE_TEXT,
  SCRIPT_OPTIONS,
  SCRIPT_VALUES,
  SCRIPT_LABELS,
  getScriptMeta,
  matchesScriptFilter,
  filterResultsByScript,
  normalizeScriptKey,
};
