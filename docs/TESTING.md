# Testing

## Unit and API suite

```bash
cd impl
ODF_DATABASE_URL=sqlite:///./odf_test.db \
ODF_JWT_SECRET=test-secret-test-secret-test-secret \
ODF_FERNET_KEY=$(python -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())') \
.venv/bin/python -m pytest -q
```

Integration tests carry the `integration` marker and skip when their
environment variables are missing. They are excluded from the fast unit run
by the skip, not by a separate test path.

## Real services

`deploy/integration/docker-compose.yml` provides:

| Profile | Services | Used for |
| --- | --- | --- |
| `core` | PostgreSQL, ClickHouse, MinIO | every push |
| `full` | core + SQL Server, Oracle Free, Keycloak, OpenLDAP | weekly / manual |
| `idp` | Keycloak, OpenLDAP | identity-only runs |

Start core services:

```bash
docker compose -f deploy/integration/docker-compose.yml --profile core up -d --wait
```

Environment variables:

```bash
ODF_IT_POSTGRES_URL=postgresql+psycopg://odf:odf@127.0.0.1:55432/odf_it
ODF_IT_CLICKHOUSE_URL=clickhouse://default:@127.0.0.1:58123/default
ODF_IT_S3_ENDPOINT=http://127.0.0.1:59010
ODF_IT_S3_BUCKET=odf-it
ODF_IT_S3_ACCESS_KEY=odfminio
ODF_IT_S3_SECRET_KEY=odfminio123
```

Full profile additionally uses:

```bash
ODF_IT_MSSQL_URL='mssql+pymssql://sa:Odf_Strong_Passw0rd!@127.0.0.1:51433/master'
ODF_IT_ORACLE_URL='oracle+oracledb://odf:Odf_Oracle_123@127.0.0.1:51521/?service_name=FREEPDB1'
ODF_IT_OIDC_ISSUER=http://127.0.0.1:58080/realms/odf
ODF_IT_OIDC_CLIENT_ID=odf
ODF_IT_OIDC_CLIENT_SECRET=odf-secret
ODF_IT_LDAP_URL=ldap://127.0.0.1:51389
ODF_IT_LDAP_USER_DN_TEMPLATE='cn={username},ou=users,dc=example,dc=org'
ODF_IT_LDAP_PASSWORD=alicepass
```

Run:

```bash
cd impl
.venv/bin/python -m pytest tests/integration -m integration -q
```

The OIDC test validates live discovery and PKCE state generation against
Keycloak; the interactive login form remains a browser/manual check.

## Browser E2E

Playwright starts `scripts/e2e_server.py`, which creates a disposable SQLite
database, seeds an admin, SQLite and file datasources, syncs metadata, and
publishes a demo pipeline.

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

Set `PYTHON=/path/to/python` if the backend interpreter is not on `PATH`
(Windows defaults to `../impl/.venv/Scripts/python.exe`).

## CI

- `.github/workflows/ci.yml`: unit/API suite, core integration matrix,
  Playwright E2E.
- `.github/workflows/integration-full.yml`: weekly full matrix including SQL
  Server, Oracle, Keycloak and OpenLDAP.

SQL Server and Oracle images are large and start slowly; they are kept out of
every-push CI on purpose.
