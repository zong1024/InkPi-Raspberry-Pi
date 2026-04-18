const path = require('node:path');

const {
  createReporter,
  exists,
  findPageEntries,
  formatMiniappPath,
  loadJson,
  loadMiniappConfig,
  logStep,
  miniappRoot,
  normalizeApiBaseUrl,
  pageFileExtensions,
  parseUrl,
} = require('./_shared');

const numericConfigKeys = [
  'POLL_INTERVAL',
  'DEFAULT_WEEKLY_GOAL',
  'RECENT_PRACTICE_LIMIT',
  'PRACTICE_RECOMMENDATION_COUNT',
  'PRACTICE_TARGET_SCORE',
  'STABLE_PRACTICE_TARGET',
  'STABLE_SCORE_LINE',
];

function validateConfig() {
  logStep('Config check: app.json, project.config.json, config.js, and page registry');

  const reporter = createReporter();
  const appConfigPath = path.join(miniappRoot, 'app.json');
  const projectConfigPath = path.join(miniappRoot, 'project.config.json');
  const sitemapPath = path.join(miniappRoot, 'sitemap.json');

  const appConfig = loadJson(appConfigPath);
  const projectConfig = loadJson(projectConfigPath);
  const runtimeConfig = loadMiniappConfig();

  const pageEntries = Array.isArray(appConfig.pages) ? appConfig.pages : [];
  if (!pageEntries.length) {
    reporter.error('app.json must register at least one page.');
  }

  const duplicatePages = pageEntries.filter((page, index) => pageEntries.indexOf(page) !== index);
  if (duplicatePages.length) {
    reporter.error(`app.json contains duplicate page entries: ${Array.from(new Set(duplicatePages)).join(', ')}`);
  }

  for (const page of pageEntries) {
    for (const extension of pageFileExtensions) {
      const targetPath = path.join(miniappRoot, `${page}${extension}`);
      if (!exists(targetPath)) {
        reporter.error(`Missing page asset: ${formatMiniappPath(targetPath)}`);
      }
    }
  }

  const discoveredPages = findPageEntries();
  const unregisteredPages = discoveredPages.filter((page) => !pageEntries.includes(page));
  if (unregisteredPages.length) {
    reporter.warn(`Found page directories not registered in app.json: ${unregisteredPages.join(', ')}`);
  }

  const missingPageDirs = pageEntries.filter((page) => !discoveredPages.includes(page));
  if (missingPageDirs.length) {
    reporter.warn(`app.json references pages outside the pages/*/index convention: ${missingPageDirs.join(', ')}`);
  }

  if (!appConfig.window || !appConfig.window.navigationBarTitleText) {
    reporter.error('app.json.window.navigationBarTitleText must be configured.');
  }

  if (appConfig.sitemapLocation !== 'sitemap.json') {
    reporter.warn(`app.json.sitemapLocation is ${JSON.stringify(appConfig.sitemapLocation)}; expected "sitemap.json".`);
  }

  if (!exists(sitemapPath)) {
    reporter.error('sitemap.json is missing.');
  }

  const apiBaseUrl = normalizeApiBaseUrl(runtimeConfig.API_BASE_URL);
  const parsedUrl = parseUrl(apiBaseUrl);
  if (!parsedUrl) {
    reporter.error(`config.js API_BASE_URL is not a valid absolute URL: ${JSON.stringify(runtimeConfig.API_BASE_URL)}`);
  } else if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    reporter.error(`config.js API_BASE_URL must use http or https: ${apiBaseUrl}`);
  }

  if (runtimeConfig.API_BASE_URL !== apiBaseUrl) {
    reporter.warn('config.js API_BASE_URL has a trailing slash; artifact packaging will normalize it.');
  }

  for (const key of numericConfigKeys) {
    const value = Number(runtimeConfig[key]);
    if (!Number.isFinite(value) || value <= 0) {
      reporter.error(`config.js ${key} must be a positive number.`);
    }
  }

  if (projectConfig.compileType !== 'miniprogram') {
    reporter.error(`project.config.json compileType must be "miniprogram", got ${JSON.stringify(projectConfig.compileType)}.`);
  }

  if (!projectConfig.appid) {
    reporter.error('project.config.json appid is required.');
  }

  if (!/^wx[a-zA-Z0-9]{16}$/.test(`${projectConfig.appid || ''}`)) {
    reporter.warn(`project.config.json appid does not match the expected Mini Program format: ${projectConfig.appid || '<empty>'}`);
  }

  if (!projectConfig.projectname) {
    reporter.warn('project.config.json projectname is empty.');
  }

  if (!projectConfig.libVersion) {
    reporter.warn('project.config.json libVersion is empty.');
  }

  const settings = projectConfig.setting || {};
  if (settings.minified !== true) {
    reporter.warn('project.config.json setting.minified is not enabled.');
  }
  if (settings.minifyWXSS !== true) {
    reporter.warn('project.config.json setting.minifyWXSS is not enabled.');
  }
  if (settings.minifyWXML !== true) {
    reporter.warn('project.config.json setting.minifyWXML is not enabled.');
  }
  if (settings.uploadWithSourceMap !== true) {
    reporter.warn('project.config.json setting.uploadWithSourceMap is not enabled.');
  }

  reporter.finalize(`Config check passed for ${pageEntries.length} registered pages.`);
}

if (require.main === module) {
  validateConfig();
}

module.exports = validateConfig;
