const fs = require('node:fs');
const path = require('node:path');

const {
  createReporter,
  formatMiniappPath,
  loadJson,
  logStep,
  miniappRoot,
  runNodeCheck,
  walkFiles,
} = require('./_shared');

const textExtensions = new Set(['.js', '.json', '.wxml', '.wxss']);
const excludedNames = new Set(['dist', 'node_modules', 'scripts']);
const mergeMarkerPattern = /^(<<<<<<<|=======|>>>>>>>)/m;

function runLint() {
  logStep('Static check: syntax, JSON parsing, and conflict markers');

  const reporter = createReporter();
  const files = walkFiles(miniappRoot, {
    excludeNames: excludedNames,
    includeExtensions: textExtensions,
  });

  let jsCount = 0;
  let jsonCount = 0;

  for (const filePath of files) {
    const relativePath = formatMiniappPath(filePath);
    const content = fs.readFileSync(filePath, 'utf8');

    if (mergeMarkerPattern.test(content)) {
      reporter.error(`${relativePath} still contains git conflict markers.`);
      continue;
    }

    const extension = path.extname(filePath);
    if (extension === '.js') {
      jsCount += 1;
      const result = runNodeCheck(filePath);
      if (result.status !== 0) {
        reporter.error(`${relativePath} failed node --check:\n${(result.stderr || result.stdout || '').trim()}`);
      }
      continue;
    }

    if (extension === '.json') {
      jsonCount += 1;
      try {
        loadJson(filePath);
      } catch (error) {
        reporter.error(`${relativePath} is not valid JSON: ${error.message}`);
      }
    }
  }

  reporter.finalize(`Static check passed for ${files.length} files (${jsCount} JS, ${jsonCount} JSON).`);
}

if (require.main === module) {
  runLint();
}

module.exports = runLint;
