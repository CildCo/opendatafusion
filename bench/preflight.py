import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bench import config


def check_budget(mem_gb: float, disk_gb: float, load1: float) -> list[str]:
    errors = []
    if mem_gb < config.BUDGET["min_free_mem_gb"]:
        errors.append(f"insufficient free memory: {mem_gb:.1f}GB")
    if disk_gb < config.BUDGET["min_free_disk_gb"]:
        errors.append(f"insufficient free disk: {disk_gb:.1f}GB")
    if load1 > config.BUDGET["max_load"]:
        errors.append(f"host load too high: {load1:.1f}")
    return errors


def _run(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, check=False, capture_output=True,
                          text=True).stdout.strip()


def _mem_available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


def _disk_free_gb(path: str = "/data") -> float:
    return shutil.disk_usage(path).free / 1e9


def _load1() -> float:
    return float(Path("/proc/loadavg").read_text().split()[0])


def collect_manifest() -> dict:
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "services": _run(
            "systemctl is-active odf-api odf-mcp odf-worker odf-scheduler").splitlines(),
        "ports": _run("ss -ltn | awk '{print $4}'").splitlines(),
        "databases": _run(
            "su - postgres -c \"psql -Atc 'select datname from pg_database order by 1'\"").splitlines(),
        "disk_free_gb": round(_disk_free_gb(), 1),
        "mem_available_gb": round(_mem_available_gb(), 1),
        "load1": _load1(),
        "failed_units": _run("systemctl --failed --no-legend").splitlines(),
    }


def main() -> int:
    errors = check_budget(_mem_available_gb(), _disk_free_gb(), _load1())
    manifest = collect_manifest()
    config.ROOT.mkdir(parents=True, exist_ok=True)
    (config.ROOT / "manifest-before.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        print("PREFLIGHT FAILED")
        for error in errors:
            print("-", error)
        return 1
    print("PREFLIGHT OK")
    print(json.dumps({k: manifest[k] for k in
                      ("services", "disk_free_gb", "mem_available_gb", "load1")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
