import argparse
from datetime import datetime, timedelta, timezone

from odf.db import SessionLocal
from odf.models import AuditLog
from odf.services.audit import export_audit, prune_audit, write_audit
from odf.services.aksk_admin import issue_aksk
from odf.services.passwords import validate_password
from odf.services.projects import create_project
from odf.services.rotation import rotate_aksk, rotate_fernet, rotate_webhook
from odf.services.users import (create_user, reset_password_by_name,
                                reset_totp_by_name, set_active_by_name)


def main():
    parser = argparse.ArgumentParser(prog="odf")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("create-admin")
    a.add_argument("--username", required=True)
    a.add_argument("--password", required=True)

    p = sub.add_parser("create-project")
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)

    su = sub.add_parser("set-user-active")
    su.add_argument("--username", required=True)
    su.add_argument("--active", choices=["true", "false"], required=True)

    rp = sub.add_parser("reset-password")
    rp.add_argument("--username", required=True)
    rp.add_argument("--password", required=True)

    rt = sub.add_parser("reset-totp")
    rt.add_argument("--username", required=True)

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

    pd = sub.add_parser("prune-data")
    pd.add_argument("--apply", action="store_true")
    pd.add_argument("--days", action="append", default=[],
                    metavar="KEY=N")
    pd.add_argument("--archive-dir")

    sub.add_parser("doctor")

    bc = sub.add_parser("backup-check")
    bc.add_argument("--path", required=True)

    args = parser.parse_args()
    with SessionLocal() as s:
        if args.cmd == "create-admin":
            validate_password(args.password)
            u = create_user(s, args.username, args.password, role="admin")
            print("created admin id=%s" % u.id)
        elif args.cmd == "create-project":
            proj = create_project(s, args.code, args.name)
            print("created project id=%s" % proj.id)
        elif args.cmd == "set-user-active":
            u = set_active_by_name(s, args.username,
                                   args.active == "true")
            write_audit(s, "cli", "set_user_active", str(u.id),
                        {"active": u.active})
            print("user id=%s active=%s" % (u.id, u.active))
        elif args.cmd == "reset-password":
            validate_password(args.password)
            u = reset_password_by_name(s, args.username, args.password)
            write_audit(s, "cli", "reset_user_password", str(u.id), {})
            print("password reset for user id=%s" % u.id)
        elif args.cmd == "reset-totp":
            u = reset_totp_by_name(s, args.username)
            write_audit(s, "cli", "reset_user_totp", str(u.id), {})
            print("two-factor cleared for user id=%s" % u.id)
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
        elif args.cmd == "doctor":
            import json
            from odf.services.doctor import check
            report = check(s)
            print(json.dumps(report, default=str, indent=2))
            if not report["ok"]:
                raise SystemExit(1)
        elif args.cmd == "backup-check":
            import json
            from odf.services.doctor import check_backup
            report = check_backup(args.path)
            print(json.dumps(report, indent=2))
            if not report["ok"]:
                raise SystemExit(1)
        elif args.cmd == "prune-data":
            from odf.services.retention import prune as prune_data
            overrides = {}
            for item in args.days:
                if "=" not in item:
                    parser.error("--days expects KEY=N")
                key, value = item.split("=", 1)
                overrides[key] = value
            try:
                result = prune_data(s, overrides, apply=args.apply,
                                    archive_dir=args.archive_dir)
            except ValueError as error:
                parser.error(str(error))
            for key, row in result.items():
                print("%-18s days=%-4s matched=%-6s removed=%s"
                      % (key, row["days"], row["matched"],
                         row["removed"]))
            if args.apply:
                from odf.services.audit import write_audit
                write_audit(s, "cli", "prune_data", "retention",
                            {"removed": {k: v["removed"]
                                         for k, v in result.items()
                                         if v["removed"]}})
            else:
                print("dry run; add --apply to delete")
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
