import argparse
import asyncio
import json
import os
import time

import httpx


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


async def run(args):
    headers = {}
    token = args.token or os.environ.get("ODF_TOKEN")
    async with httpx.AsyncClient(
            base_url=args.base, timeout=args.timeout,
            limits=httpx.Limits(
                max_connections=args.concurrency,
                max_keepalive_connections=0)) as c:
        if not token and args.username:
            r = await c.post("/api/v1/auth/login", json={
                "username": args.username, "password": args.password,
                "project_id": args.project})
            r.raise_for_status()
            token = r.json()["token"]
        if token:
            headers["Authorization"] = "Bearer " + token
        sem = asyncio.Semaphore(args.concurrency)

        async def one():
            async with sem:
                started = time.perf_counter()
                try:
                    r = await c.get(args.path, headers=headers)
                    return r.status_code, time.perf_counter() - started
                except Exception:
                    return 0, time.perf_counter() - started

        started = time.perf_counter()
        results = await asyncio.gather(
            *(one() for _ in range(args.requests)))
        elapsed = time.perf_counter() - started

    latencies = [ms * 1000 for _, ms in results]
    statuses = {}
    for code, _ in results:
        statuses[str(code)] = statuses.get(str(code), 0) + 1
    errors = statuses.get("0", 0) + sum(
        n for code, n in statuses.items()
        if code != "0" and int(code) >= 400)
    return {
        "path": args.path, "requests": args.requests,
        "concurrency": args.concurrency, "seconds": round(elapsed, 3),
        "rps": round(args.requests / elapsed, 1) if elapsed else 0,
        "errors": errors, "statuses": statuses,
        "p50_ms": round(percentile(latencies, 50), 2),
        "p95_ms": round(percentile(latencies, 95), 2),
        "p99_ms": round(percentile(latencies, 99), 2),
        "max_ms": round(max(latencies or [0]), 2),
    }


def main():
    p = argparse.ArgumentParser(prog="loadtest")
    p.add_argument("--base", default="http://127.0.0.1:18080")
    p.add_argument("--path", default="/api/v1/health/snapshot")
    p.add_argument("--token", default="")
    p.add_argument("--username", default="")
    p.add_argument("--password", default="")
    p.add_argument("--project", type=int, default=1)
    p.add_argument("--requests", type=int, default=200)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--timeout", type=float, default=30)
    args = p.parse_args()
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
