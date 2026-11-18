"""Run one statement through the Trino REST API and print rows as TSV."""
import json
import sys
import time
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def _same_origin(base: str, uri: str) -> str:
    """Follow nextUri through the same host we called; a coordinator behind a
    service may advertise its pod address instead."""
    parts = urlsplit(uri)
    root = urlsplit(base)
    return urlunsplit((root.scheme, root.netloc, parts.path, parts.query, ""))


def main() -> int:
    base, user, query = sys.argv[1], sys.argv[2], sys.argv[3]
    request = urllib.request.Request(
        base.rstrip("/") + "/v1/statement", data=query.encode(),
        headers={"X-Trino-User": user, "Content-Type": "text/plain"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        while True:
            if payload.get("error"):
                print(payload["error"].get("message", "query failed"),
                      file=sys.stderr)
                return 1
            for row in payload.get("data") or []:
                print("\t".join(str(value) for value in row))
            next_uri = payload.get("nextUri")
            if not next_uri:
                return 0
            time.sleep(0.2)
            with urllib.request.urlopen(_same_origin(base, next_uri),
                                        timeout=60) as response:
                payload = json.load(response)
    except Exception as error:
        print("query failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
