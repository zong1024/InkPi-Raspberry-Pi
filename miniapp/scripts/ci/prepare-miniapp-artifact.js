const fs = require('node:fs');
const path = require('node:path');

const {
  artifactRoot,
  copyTree,
  ensureDir,
  getGitSha,
  loadJson,
  loadMiniappConfig,
  logStep,
  miniappRoot,
  normalizeApiBaseUrl,
  parseArgs,
  resetDir,
  writeGeneratedConfig,
} = require('./_shared');

const excludedNames = new Set([
  '.gitignore',
  'README.md',
  'dist',
  'node_modules',
  'package-lock.json',
  'package.json',
  'scripts',
]);

function prepareArtifact(options = parseArgs()) {
  logStep('Artifact prep: copy source package and generate build metadata');

  const sourceConfig = loadMiniappConfig();
  const overrideApiBaseUrl = normalizeApiBaseUrl(process.env.MINIAPP_API_BASE_URL || '');
  const artifactConfig = {
    ...sourceConfig,
    API_BASE_URL: overrideApiBaseUrl || normalizeApiBaseUrl(sourceConfig.API_BASE_URL),
  };

  resetDir(artifactRoot);
  copyTree(miniappRoot, artifactRoot, { excludeNames: excludedNames });
  ensureDir(artifactRoot);
  writeGeneratedConfig(path.join(artifactRoot, 'config.js'), artifactConfig);

  const appConfig = loadJson(path.join(miniappRoot, 'app.json'));
  const buildMetadata = {
    builtAt: new Date().toISOString(),
    gitSha: getGitSha(),
    releaseMode: Boolean(options.release),
    artifactRoot: 'miniapp/dist/ci-package',
    apiBaseUrl: artifactConfig.API_BASE_URL,
    pageCount: Array.isArray(appConfig.pages) ? appConfig.pages.length : 0,
    workflowRunId: process.env.GITHUB_RUN_ID || null,
    workflowRunNumber: process.env.GITHUB_RUN_NUMBER || null,
  };

  fs.writeFileSync(
    path.join(artifactRoot, 'build-meta.json'),
    `${JSON.stringify(buildMetadata, null, 2)}\n`,
    'utf8'
  );

  console.log(`[miniapp-ci] Artifact prepared at ${artifactRoot}`);
}

if (require.main === module) {
  prepareArtifact();
}

module.exports = prepareArtifact;
