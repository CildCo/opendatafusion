# Frontend

The console is a Vue 3 single-page application built with Vite and served by
the FastAPI process at `/ui/`.

## Development

```bash
npm ci
npm run dev
```

The dev server proxies API calls to `http://127.0.0.1:18080`. Start the backend
first (see the root README).

## Build

```bash
npm run build
```

The build is written to `../impl/odf/static` and is served by the API. Use
`npm run preview` to inspect a production build locally.

## Browser tests

Playwright starts a disposable backend from `../scripts/e2e_server.py`.

```bash
npx playwright install chromium
npm run test:e2e
```

The acceptance suite uses an external acceptance environment and is run only
when `playwright.acceptance.config.js` points at one.

## Structure

- `src/views/` — routed pages (datasources, catalog, pipelines, APIs, models,
  dashboards, apps, operations, governance, workspace).
- `src/studio/` — shared editors and runtime shells.
- `src/styles.css` — the design tokens, Element Plus overrides and shared
  layout grammar.
- `e2e/` — Playwright specs.
