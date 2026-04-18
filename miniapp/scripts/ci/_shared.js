const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const miniappRoot = path.resolve(__dirname, '..', '..');
const artifactRoot = path.join(miniappRoot, 'dist', 'ci-package');
const pageFileExtensions = ['.js', '.json', '.wxml', '.wxss'];
const requiredArtifactFiles = [
  'app.js',
  'app.json',
  'app.wxss',
  'config.js',
  'project.config.json',
  'sitemap.json',
];

function parseArgs(argv = process.argv.slice(2)) {
  return {
    release: argv.includes('--release'),
  };
}

function logStep(message) {
  console.log(`\n[miniapp-ci] ${message}`);
}

function exists(targetPath) {
  return fs.existsSync(targetPath);
}

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function resetDir(targetPath) {
  fs.rmSync(targetPath, { recursive: true, force: true });
  ensureDir(targetPath);
}

function loadJson(targetPath) {
  return JSON.parse(fs.readFileSync(targetPath, 'utf8'));
}

function loadMiniappConfig(configPath = path.join(miniappRoot, 'config.js')) {
  const resolvedPath = require.resolve(configPath);
  delete require.cache[resolvedPath];
  return require(resolvedPath);
}

function walkFiles(rootDir, options = {}) {
  const { excludeNames = new Set(), includeExtensions = null } = options;
  const files = [];

  function walk(currentDir) {
    for (const entry of fs.readdirSync(currentDir, { withFileTypes: true })) {
      if (excludeNames.has(entry.name)) {
        continue;
      }

      const absolutePath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        walk(absolutePath);
        continue;
      }

      if (includeExtensions && !includeExtensions.has(path.extname(entry.name))) {
        continue;
      }

      files.push(absolutePath);
    }
  }

  if (exists(rootDir)) {
    walk(rootDir);
  }

  return files.sort();
}

function formatMiniappPath(targetPath, rootDir = miniappRoot) {
  return path.relative(rootDir, targetPath).split(path.sep).join('/');
}

function findPageEntries(rootDir = miniappRoot) {
  const pagesDir = path.join(rootDir, 'pages');
  if (!exists(pagesDir)) {
    return [];
  }

  return fs
    .readdirSync(pagesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => `pages/${entry.name}/index`)
    .sort();
}

function runNodeCheck(targetPath) {
  return spawnSync(process.execPath, ['--check', targetPath], {
    encoding: 'utf8',
  });
}

function normalizeApiBaseUrl(urlText) {
  return `${urlText || ''}`.trim().replace(/\/+$/, '');
}

function parseUrl(urlText) {
  try {
    return new URL(urlText);
  } catch (error) {
    return null;
  }
}

function isLoopbackHost(hostname) {
  const normalized = `${hostname || ''}`.toLowerCase();
  return normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '0.0.0.0' || normalized === '::1';
}

function isIpv4Host(hostname) {
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname);
}

function isIpv6Host(hostname) {
  return hostname.includes(':');
}

function isIpHost(hostname) {
  return isIpv4Host(hostname) || isIpv6Host(hostname);
}

function copyTree(sourceDir, targetDir, options = {}) {
  const { excludeNames = new Set() } = options;
  ensureDir(targetDir);

  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    if (excludeNames.has(entry.name)) {
      continue;
    }

    const sourcePath = path.join(sourceDir, entry.name);
    const targetPath = path.join(targetDir, entry.name);

    if (entry.isDirectory()) {
      copyTree(sourcePath, targetPath, options);
      continue;
    }

    ensureDir(path.dirname(targetPath));
    fs.copyFileSync(sourcePath, targetPath);
  }
}

function writeGeneratedConfig(targetPath, config) {
  const declarations = Object.entries(config)
    .map(([key, value]) => `const ${key} = ${JSON.stringify(value)};`)
    .join('\n');

  const exportBlock = `module.exports = {\n${Object.keys(config)
    .map((key) => `  ${key},`)
    .join('\n')}\n};\n`;

  fs.writeFileSync(targetPath, `${declarations}\n\n${exportBlock}`, 'utf8');
}

function getGitSha() {
  if (process.env.GITHUB_SHA) {
    return process.env.GITHUB_SHA.slice(0, 12);
  }

  const result = spawnSync('git', ['rev-parse', '--short=12', 'HEAD'], {
    cwd: path.resolve(miniappRoot, '..'),
    encoding: 'utf8',
  });

  if (result.status === 0) {
    return result.stdout.trim();
  }

  return 'unknown';
}

function createReporter() {
  const warnings = [];
  const errors = [];

  return {
    warn(message) {
      warnings.push(message);
    },
    error(message) {
      errors.push(message);
    },
    finalize(successMessage) {
      if (warnings.length) {
        console.warn('[miniapp-ci] Warnings:');
        for (const warning of warnings) {
          console.warn(`  - ${warning}`);
        }
      }

      if (errors.length) {
        const errorMessage = errors.map((item) => `- ${item}`).join('\n');
        throw new Error(`[miniapp-ci] Checks failed:\n${errorMessage}`);
      }

      if (successMessage) {
        console.log(`[miniapp-ci] ${successMessage}`);
      }

      return { warnings, errors };
    },
    warnings,
    errors,
  };
}

module.exports = {
  artifactRoot,
  createReporter,
  copyTree,
  ensureDir,
  exists,
  findPageEntries,
  formatMiniappPath,
  getGitSha,
  loadJson,
  loadMiniappConfig,
  logStep,
  miniappRoot,
  normalizeApiBaseUrl,
  pageFileExtensions,
  parseArgs,
  parseUrl,
  requiredArtifactFiles,
  resetDir,
  runNodeCheck,
  walkFiles,
  writeGeneratedConfig,
  isIpHost,
  isLoopbackHost,
};
