"""Check every API replica behind a load balancer.

Usage:
    python scripts/ha_smoke.py --url http://api-1:18080 \
        --url http://api-2:18080 --url http://api-3:18080

Each replica must answer /livez and /readyz with HTTP 200. Exit code 1 when
any check fails.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def check(url, path, timeout):
    target = url.rstrip("/") + path
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            body = response.read(512).decode("utf-8", "replace")
            return response.status == 200, body.strip()
    except urllib.error.HTTPError as error:
        return False, "HTTP %s" % error.code
    except Exception as error:
        return False, type(error).__name__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    failures = 0
    for url in args.url:
        for path in ("/livez", "/readyz"):
            ok, detail = check(url, path, args.timeout)
            print("%-32s %-7s %s %s" % (url, path, "ok" if ok else "FAIL",
                                        detail[:80]))
            if not ok:
                failures += 1
    print(json.dumps({"replicas": len(args.url), "failures": failures}))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
