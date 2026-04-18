# MiniApp CI/CD

This directory now contains a lightweight Node-based CI/CD guardrail for the WeChat Mini Program source.

The pipeline is organized in four stages:

1. `npm run lint`
   Checks JavaScript syntax with `node --check`, parses every JSON file, and blocks merge-conflict markers.
2. `npm run check:config`
   Verifies `app.json`, `project.config.json`, `config.js`, the registered page list, and required page assets.
3. `npm run prepare:artifact`
   Copies a clean package into `miniapp/dist/ci-package`, regenerates `config.js`, and writes `build-meta.json`.
4. `npm run check:preflight`
   Validates the prepared artifact before release handoff.

Common entrypoints:

```bash
npm --prefix miniapp run ci
npm --prefix miniapp run ci:release
```

`ci` is the default pull request / branch pipeline. It allows non-release API endpoints but will warn when the artifact still points to localhost or a raw IP.

`ci:release` turns on strict release gating:

- `API_BASE_URL` must be `https`
- `API_BASE_URL` must use a public domain instead of localhost or a raw IP
- `project.config.json` must keep minification enabled
- the packaged artifact must contain the full page set declared in `app.json`

Optional artifact override:

```bash
MINIAPP_API_BASE_URL=https://miniapp.example.com npm --prefix miniapp run ci:release
```

This environment variable only rewrites `miniapp/dist/ci-package/config.js`. The source `miniapp/config.js` file is left unchanged so the working tree stays stable for local development.

Generated output:

- Artifact folder: `miniapp/dist/ci-package`
- Build metadata: `miniapp/dist/ci-package/build-meta.json`
- Preflight report: `miniapp/dist/ci-package/preflight-report.json`

GitHub Actions integration lives in `.github/workflows/miniapp-ci.yml`.
