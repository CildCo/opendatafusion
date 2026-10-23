import asyncio
import time
from random import Random

import httpx

from bench.load import scenarios


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int((len(ordered) - 1) * pct / 100))
    return ordered[idx]


def summarize(results) -> dict:
    rows = [(r[0], r[1], r[2] if len(r) > 2 else "all") for r in results]
    latencies = [ms for _, ms, _ in rows]
    errors = sum(1 for status, _, _ in rows if status == 0 or status >= 400)
    by_kind = {}
    for kind in sorted({k for _, _, k in rows}):
        subset = [(s, ms) for s, ms, k in rows if k == kind]
        by_kind[kind] = summarize_simple(subset)
    return {"count": len(rows), "errors": errors,
            "p50_ms": round(percentile(latencies, 50), 2),
            "p95_ms": round(percentile(latencies, 95), 2),
            "p99_ms": round(percentile(latencies, 99), 2),
            "by_kind": by_kind}


def summarize_simple(results: list[tuple[int, float]]) -> dict:
    latencies = [ms for _, ms in results]
    errors = sum(1 for status, _ in results if status == 0 or status >= 400)
    return {"count": len(results), "errors": errors,
            "p50_ms": round(percentile(latencies, 50), 2),
            "p95_ms": round(percentile(latencies, 95), 2),
            "p99_ms": round(percentile(latencies, 99), 2)}


def scenario_request(kind: str, ids: dict | None = None):
    ids = ids or {}
    if kind == "dataset_preview" and ids.get("dataset"):
        return "POST", f"/api/v1/datasets/{ids['dataset']}/preview", {
            "limit": 20}
    if kind == "metric" and ids.get("metric"):
        return "POST", f"/api/v1/metrics/{ids['metric']}/query", {"limit": 10}
    if kind == "dashboard" and ids.get("dashboard"):
        return "POST", f"/api/v1/dashboards/{ids['dashboard']}/data", {}
    if kind == "catalog":
        return "GET", "/api/v1/catalog/search", {"q": "订单"}
    if kind == "dataset_list":
        return "GET", "/api/v1/datasets", None
    if kind == "ops":
        return "GET", "/api/v1/ops/summary", None
    return "GET", "/api/v1/mcp/tools", None


async def _one(client: httpx.AsyncClient, token: str, rng: Random,
               ids: dict | None) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        kind = scenarios.pick(rng)
        method, path, payload = scenario_request(kind, ids)
        kwargs = {"headers": {"Authorization": "Bearer " + token}}
        if method == "POST":
            kwargs["json"] = payload
        elif payload:
            kwargs["params"] = payload
        r = await client.request(method, path, **kwargs)
        return (r.status_code, (time.perf_counter() - started) * 1000, kind)
    except Exception:
        return (0, (time.perf_counter() - started) * 1000, kind)


async def run(base_url: str, token: str, users: int, seconds: int,
              ids: dict | None = None, stop_event=None) -> dict:
    rng = Random(20261022)
    results = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        end = time.time() + seconds

        async def worker() -> None:
            while time.time() < end and not (
                    stop_event and stop_event.is_set()):
                results.append(await _one(client, token, rng, ids))

        await asyncio.gather(*(worker() for _ in range(users)))
    return summarize(results)
