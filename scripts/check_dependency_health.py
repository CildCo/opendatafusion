#!/usr/bin/env python3
"""Report scheduled runs skipped because an upstream dependency was missing.

Exits 1 when at least one downstream job was blocked in the window, so it
can run from cron or a monitoring job.
"""
import argparse
import json
import sys

from odf.db import SessionLocal
from odf.services.dependencies import recent_blocked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project", type=int, default=None)
    args = parser.parse_args()
    with SessionLocal() as session:
        rows = recent_blocked(session, args.project, args.hours, args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        if not rows:
            print("no dependency-blocked runs in the last %dh" % args.hours)
        for row in rows:
            print("%s %s #%s skipped at %s: %s" % (
                row["type"], row["name"], row["object_id"], row["at"],
                row["reason"]))
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
