# High availability and backup

## Topology

- Run **N API replicas** behind a load balancer. Use `GET /livez` for
  liveness and `GET /readyz` for readiness (checks PostgreSQL and returns 503
  when it cannot connect).
- Run **one scheduler leader**; the scheduler uses a PostgreSQL advisory lock
  (`999999`), so extra replicas exit with "another scheduler is already leader".
- Run **N workers**; jobs are claimed with `FOR UPDATE SKIP LOCKED`, so workers
  scale horizontally. Set a unique `ODF_WORKER_ID`.
- Use PostgreSQL 14+ with backups enabled. The queue is the `job` table; no
  external broker is required.
- Mount `ODF_FILE_DIR` on shared storage (NFS or the S3 backend) for multi-API
  deployments.
- MCP streamable HTTP (`18082`) can run one replica or sit behind the same LB.

## Backup

```bash
ODF_DATABASE_URL='postgresql+psycopg://user:pass@host/odf' \
ODF_FILE_DIR=/data/odf/files ./scripts/backup.sh /backups
```

The script writes `odf-<timestamp>.tar.gz` (pg_dump + files) and a SHA-256
sidecar, keeping `ODF_BACKUP_KEEP` archives (default 14). Store both off-host.
`restore.sh` verifies the sidecar before overwriting anything. Test restores
quarterly.

Install the provided timers for unattended operation:

```bash
sudo cp deploy/systemd/odf-backup.* deploy/systemd/odf-audit-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now odf-backup.timer odf-audit-prune.timer
```

`prune-audit.sh` exports older audit rows to JSONL and then deletes them
(`ODF_AUDIT_RETENTION_DAYS`, default 180); audit archive files are kept for
`ODF_AUDIT_KEEP_DAYS` (default 365).

## Restore

```bash
ODF_DATABASE_URL='postgresql+psycopg://user:pass@host/odf' \
ODF_FILE_DIR=/data/odf/files ./scripts/restore.sh /backups/odf-....tar.gz --yes
```

Stop API/worker/scheduler before restore, then run `alembic upgrade head` and
restart. Restore overwrites the database and file directory.
