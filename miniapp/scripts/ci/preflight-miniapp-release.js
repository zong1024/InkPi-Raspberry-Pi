const fs = require('node:fs');
const path = require('node:path');

const {
  artifactRoot,
  createReporter,
  exists,
  loadJson,
  loadMiniappConfig,
  logStep,
  pageFileExtensions,
  parseArgs,
  parseUrl,
  requiredArtifactFiles,
  isIpHost,
  isLoopbackHost,
} = require('./_shared');

function preflight(options = parseArgs()) {
  logStep(options.release ? 'Pre-release check: strict release gating' : 'Pre-release check: CI artifact sanity');

  const reporter = createReporter();

  if (!exists(artifactRoot)) {
    reporter.error('Artifact directory is missing. Run prepare:artifact before preflight.');
    reporter.finalize();
    return;
  }

  for (const requiredFile of requiredArtifactFiles) {
    const targetPath = path.join(artifactRoot, requiredFile);
    if (!exists(targetPath)) {
      reporter.error(`Artifact is missing ${requiredFile}.`);
    }
  }

  const reportPath = path.join(artifactRoot, 'preflight-report.json');
  let appConfig = null;
  let projectConfig = null;
  let runtimeConfig = null;

  if (reporter.errors.length === 0) {
    appConfig = loadJson(path.join(artifactRoot, 'app.json'));
    projectConfig = loadJson(path.join(artifactRoot, 'project.config.json'));
    runtimeConfig = loadMiniappConfig(path.join(artifactRoot, 'config.js'));

    for (const page of appConfig.pages || []) {
      for (const extension of pageFileExtensions) {
        const targetPath = path.join(artifactRoot, `${page}${extension}`);
        if (!exists(targetPath)) {
          reporter.error(`Artifact page file is missing: ${page}${extension}`);
        }
      }
    }

    const parsedUrl = parseUrl(runtimeConfig.API_BASE_URL);
    if (!parsedUrl) {
      reporter.error(`Artifact API_BASE_URL is invalid: ${JSON.stringify(runtimeConfig.API_BASE_URL)}`);
    } else {
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
        reporter.error(`Artifact API_BASE_URL must use http or https: ${runtimeConfig.API_BASE_URL}`);
      }

      if (!options.release && (isLoopbackHost(parsedUrl.hostname) || isIpHost(parsedUrl.hostname))) {
        reporter.warn(`Artifact API_BASE_URL points to a local or raw IP host (${parsedUrl.hostname}); this is acceptable for CI but not for release.`);
      }

      if (options.release) {
        if (parsedUrl.protocol !== 'https:') {
          reporter.error(`Release mode requires an https API_BASE_URL, got ${runtimeConfig.API_BASE_URL}`);
        }

        if (isLoopbackHost(parsedUrl.hostname) || isIpHost(parsedUrl.hostname)) {
          reporter.error(`Release mode requires a public domain name, got ${parsedUrl.hostname}`);
        }
      }
    }

    if (projectConfig.compileType !== 'miniprogram') {
      reporter.error(`Artifact compileType must stay "miniprogram", got ${JSON.stringify(projectConfig.compileType)}.`);
    }

    if (!projectConfig.appid) {
      reporter.error('Artifact appid is empty.');
    }

    if (options.release && !/^wx[a-zA-Z0-9]{16}$/.test(`${projectConfig.appid || ''}`)) {
      reporter.error(`Release mode requires a valid Mini Program appid, got ${projectConfig.appid || '<empty>'}`);
    }

    if (!projectConfig.projectname) {
      reporter.warn('Artifact projectname is empty.');
    }

    const settings = projectConfig.setting || {};
    if (options.release && settings.minified !== true) {
      reporter.error('Release mode requires setting.minified to be enabled.');
    }
    if (options.release && settings.minifyWXSS !== true) {
      reporter.error('Release mode requires setting.minifyWXSS to be enabled.');
    }
    if (options.release && settings.minifyWXML !== true) {
      reporter.error('Release mode requires setting.minifyWXML to be enabled.');
    }
    if (settings.uploadWithSourceMap !== true) {
      reporter.warn('setting.uploadWithSourceMap is disabled; post-release debugging will be harder.');
    }
  }

  const report = {
    generatedAt: new Date().toISOString(),
    mode: options.release ? 'release' : 'ci',
    passed: reporter.errors.length === 0,
    warnings: reporter.warnings,
    errors: reporter.errors,
    summary: {
      artifactRoot: 'miniapp/dist/ci-package',
      appid: projectConfig && projectConfig.appid ? projectConfig.appid : null,
      apiBaseUrl: runtimeConfig && runtimeConfig.API_BASE_URL ? runtimeConfig.API_BASE_URL : null,
      pageCount: appConfig && Array.isArray(appConfig.pages) ? appConfig.pages.length : 0,
    },
  };

  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  reporter.finalize(`Preflight check passed in ${report.mode} mode.`);
}

if (require.main === module) {
  preflight();
}

module.exports = preflight;
