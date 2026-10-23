import argparse
from datetime import datetime, timedelta, timezone

from odf.db import SessionLocal
from odf.models import AuditLog
from odf.services.audit import export_audit, prune_audit, write_audit
from odf.services.aksk_admin import issue_aksk
from odf.services.passwords import validate_password
from odf.services.projects import create_project
from odf.services.rotation import rotate_aksk, rotate_fernet, rotate_webhook
from odf.services.users import create_user


def main():
    parser = argparse.ArgumentParser(prog="odf")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("create-admin")
    a.add_argument("--username", required=True)
    a.add_argument("--password", required=True)

    p = sub.add_parser("create-project")
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)

    k = sub.add_parser("issue-aksk")
    k.add_argument("--project-id", type=int, required=True)

    rf = sub.add_parser("rotate-fernet")
    rf.add_argument("--old-key", required=True)
    rf.add_argument("--new-key", required=True)

    ra = sub.add_parser("rotate-aksk")
    ra.add_argument("--project-id", type=int, required=True)

    rw = sub.add_parser("rotate-webhook-secret")
    rw.add_argument("--project-id", type=int, required=True)
    rw.add_argument("--id", type=int, required=True)

    sub.add_parser("rotate-jwt-secret")

    pa = sub.add_parser("prune-audit")
    pa.add_argument("--days", type=int, required=True)
    pa.add_argument("--export")
    pa.add_argument("--apply", action="store_true")

    args = parser.parse_args()
    with SessionLocal() as s:
        if args.cmd == "create-admin":
            validate_password(args.password)
            u = create_user(s, args.username, args.password, role="admin")
            print("created admin id=%s" % u.id)
        elif args.cmd == "create-project":
            proj = create_project(s, args.code, args.name)
            print("created project id=%s" % proj.id)
        elif args.cmd == "issue-aksk":
            row, sk = issue_aksk(s, args.project_id)
            print("ak=%s\nsk=%s" % (row.ak, sk))
        elif args.cmd == "rotate-fernet":
            print(rotate_fernet(s, args.old_key, args.new_key))
            print("Update ODF_FERNET_KEY and restart services.")
        elif args.cmd == "rotate-aksk":
            out = rotate_aksk(s, args.project_id)
            print("ak=%s\nsk=%s" % (out["ak"], out["sk"]))
        elif args.cmd == "rotate-webhook-secret":
            out = rotate_webhook(s, args.project_id, args.id)
            print("webhook=%s secret=%s" % (out["id"], out["secret"]))
        elif args.cmd == "rotate-jwt-secret":
            print("Change ODF_JWT_SECRET and restart API/MCP. All sessions "
                  "will be invalidated.")
        elif args.cmd == "prune-audit":
            if args.days < 1:
                parser.error("--days must be at least 1")
            before = datetime.now(timezone.utc) - timedelta(days=args.days)
            total = (s.query(AuditLog)
                     .filter(AuditLog.at < before).count())
            exported = export_audit(s, before, args.export) if args.export                 else 0
            removed = prune_audit(s, before) if args.apply else 0
            if args.apply:
                write_audit(s, "cli", "prune_audit", "audit",
                            {"before": before.isoformat(), "removed": removed,
                             "exported": exported})
            print("cutoff=%s matched=%d exported=%d removed=%d"
                  % (before.isoformat(), total, exported, removed))
            if not args.apply:
                print("dry run; add --apply to delete")


if __name__ == "__main__":
    main()
