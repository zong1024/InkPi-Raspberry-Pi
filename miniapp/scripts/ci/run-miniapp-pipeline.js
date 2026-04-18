const { logStep, parseArgs } = require('./_shared');
const lintMiniapp = require('./lint-miniapp');
const validateConfig = require('./validate-miniapp-config');
const prepareArtifact = require('./prepare-miniapp-artifact');
const preflight = require('./preflight-miniapp-release');

function runPipeline(options = parseArgs()) {
  logStep(`Pipeline start (${options.release ? 'release' : 'ci'} mode)`);

  lintMiniapp(options);
  validateConfig(options);
  prepareArtifact(options);
  preflight(options);

  console.log('\n[miniapp-ci] Pipeline completed successfully.');
}

if (require.main === module) {
  runPipeline();
}

module.exports = runPipeline;
