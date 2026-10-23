#!/bin/sh
# deploy/tests/test_units.sh
set -e
for f in deploy/systemd/odf-api.service deploy/systemd/odf-mcp.service deploy/systemd/odf-worker.service deploy/systemd/odf-scheduler.service; do
  test -f "$f"
  grep -q 'MemoryMax=' "$f"
  grep -q 'User=odf' "$f"
done
for f in deploy/systemd/odf-backup.service deploy/systemd/odf-backup.timer          deploy/systemd/odf-audit-prune.service          deploy/systemd/odf-audit-prune.timer; do
  test -f "$f"
done
grep -q 'ExecStart=' deploy/systemd/odf-backup.service
grep -q 'OnCalendar=' deploy/systemd/odf-backup.timer
echo OK
