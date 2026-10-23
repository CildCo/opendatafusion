# Contributing to OpenDataFusion

Thank you for improving OpenDataFusion. This document describes the local
workflow, the quality gates and the review expectations.

## Before you start

- Search existing [issues](https://github.com/CildCo/opendatafusion/issues)
  and [discussions](https://github.com/CildCo/opendatafusion/discussions).
- For a security issue, follow [SECURITY.md](SECURITY.md) instead of opening a
  public issue.
- For a large feature or an interface change, open a discussion first so the
  design can be agreed before implementation.

## Development setup

```bash
cd impl
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
# set ODF_DATABASE_URL, ODF_JWT_SECRET and ODF_FERNET_KEY
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run dev      # proxy to http://127.0.0.1:18080
npm run build
```

Database changes use Alembic. Add a migration, run it against a scratch
PostgreSQL database, and never edit an already released migration.

## Quality gates

Every pull request must pass:

- `pytest -q` from `impl/`
- `npm run build` from `frontend/`
- Playwright E2E when the change touches the console
- `helm lint deploy/helm/odf`
- CodeQL and dependency review in CI

Keep the tests close to the behavior. A bug fix starts with a failing test.
Performance work includes a before/after measurement and the command used.

## Pull requests

- Use a focused branch and a clear title.
- Explain the problem, the chosen approach and the trade-offs.
- Include tests for new behavior and edge cases.
- Update public documentation when behavior or configuration changes.
- Keep commits reviewable; a signed-off commit (`git commit -s`) is welcome.
- Do not commit credentials, production hostnames, database dumps or customer
  data. Use the example environment files for configuration.

## Review

Maintainers review for correctness, security, backwards compatibility,
operability and test quality. A review may ask for a smaller change, a
benchmark or a design note. Approval is required before merge; see
[GOVERNANCE.md](GOVERNANCE.md).

## License

By contributing, you agree that your contribution is licensed under the
Apache License 2.0 and that you have the right to submit it.
