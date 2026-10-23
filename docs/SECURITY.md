# Security operations

## Outbound network access

- HTTP datasources and HTTP sinks perform DNS resolution once and connect to
  the resolved IP with TLS SNI preserved, preventing DNS rebinding.
- Private, loopback, link-local, reserved, multicast and unspecified addresses
  are rejected by default. Enable `ODF_HTTP_ALLOW_PRIVATE=true` only on a
  trusted network.
- `ODF_HTTP_ALLOWED_HOSTS` narrows outbound calls to exact hosts or
  `*.suffix` patterns.
- Webhooks share the same resolver with their own `ODF_WEBHOOK_ALLOW_PRIVATE`
  switch and a 64 KB payload cap.
- File datasources resolve symlinks and must sit under
  `ODF_FILE_SOURCE_ROOTS` (default `ODF_FILE_DIR`). DuckDB external access is
  disabled and configuration is locked after the file is materialized.

## Sessions

- JWTs carry `ver`. Password change and admin password reset increment the
  user's `token_version`, invalidating every existing session immediately.
- Deactivating a user invalidates sessions on the next request.
- Change `ODF_JWT_SECRET` to invalidate every session globally.
- TOTP replay is blocked by storing the last accepted time step.

## API credentials

- OpenAPI calls verify HMAC-SHA256 by default. HMAC-SHA1 is still accepted for
  compatibility; set `ODF_AKSK_ALLOW_SHA1=false` to require SHA256.
- Each AK can have an IP allowlist and per-minute rate limit.
- Rotate with `python -m odf.cli rotate-aksk --project-id N`; the old AK is
  disabled immediately.

## Audit retention

- `python -m odf.cli prune-audit --days 180 --export /backups/audit.jsonl
  --apply` exports then deletes older audit rows in batches and writes an
  audit entry for the operation itself.
- The weekly `odf-audit-prune.timer` runs `scripts/prune-audit.sh`, which keeps
  JSONL archives for `ODF_AUDIT_KEEP_DAYS` (default 365).

## Backups

- `odf-backup.timer` runs daily at 02:17 local time.
- Archives include PostgreSQL and `ODF_FILE_DIR`, with a SHA-256 sidecar.
- `restore.sh` verifies the checksum before overwriting, then run
  `alembic upgrade head` and restart services.
- Test a restore at least quarterly.

## Probes and monitoring

- `GET /livez` is process liveness; `GET /readyz` checks PostgreSQL and is the
  load-balancer readiness probe. Both are unauthenticated.
- `/metrics` exposes counters; restrict it at the network layer if exposed.
