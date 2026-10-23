import shutil
import threading
import time
from pathlib import Path

import httpx

from bench import config

LAST_ERRORS: list[str] = []


def check(mem_gb: float, disk_gb: float, load1: float,
          prod_ready: int | None = None) -> list[str]:
    errors = []
    if mem_gb < config.BUDGET["min_free_mem_gb"]:
        errors.append(f"memory: {mem_gb:.1f}GB")
    if disk_gb < config.BUDGET["min_free_disk_gb"]:
        errors.append(f"disk: {disk_gb:.1f}GB")
    if load1 > config.BUDGET["max_load"]:
        errors.append(f"load: {load1:.1f}")
    if prod_ready is not None and prod_ready != 200:
        errors.append(f"production readyz: {prod_ready}")
    return errors


def snapshot() -> list[str]:
    mem = 0.0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            mem = int(line.split()[1]) / 1024 / 1024
    disk = shutil.disk_usage("/").free / 1e9
    load = float(Path("/proc/loadavg").read_text().split()[0])
    try:
        ready = httpx.get("http://127.0.0.1:18080/readyz",
                          timeout=5).status_code
    except Exception:
        ready = None
    errors = check(mem, disk, load, ready)
    LAST_ERRORS[:] = errors
    return errors


def start(stop_event: threading.Event, interval: int = 30) -> threading.Thread:
    def loop():
        while not stop_event.is_set():
            if snapshot():
                stop_event.set()
                return
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
