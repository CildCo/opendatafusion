import json
from pathlib import Path

GATES = {"p95_ms": 500, "error_rate": 0.01}


def build(results: dict) -> dict:
    checks = results.get("checks") or []
    load = results.get("load") or {}
    loads = [load] if "p95_ms" in load else [
        v for v in load.values() if isinstance(v, dict)]
    p95 = max((x.get("p95_ms", 0) for x in loads), default=0)
    errors = sum(x.get("errors", 0) for x in loads)
    count = sum(x.get("count", 0) for x in loads)
    passed = (not checks
              and p95 <= GATES["p95_ms"]
              and errors / max(1, count) <= GATES["error_rate"])
    return {**results, "passed": passed,
            "aggregate": {"p95_ms": p95, "errors": errors, "count": count}}


def markdown(report: dict) -> str:
    lines = ["# 30GB OpenDataFusion benchmark", "",
             f"- passed: **{report['passed']}**", ""]
    for key, value in (report.get("load") or {}).items():
        lines.append(f"- {key}: {value}")
    if report.get("checks"):
        lines += ["", "## Failures"] + [f"- {x}" for x in report["checks"]]
    return "\n".join(lines) + "\n"


def write(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    path.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
