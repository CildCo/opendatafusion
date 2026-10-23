import os
import subprocess
from pathlib import Path

from bench import config

PG_BIN = os.environ.get("ODF_BENCH_PG_BIN", "/opt/pgsql-14.5/bin")


def _as_odf(cmd: list[str]) -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["runuser", "-u", "odf", "--"] + cmd
    return cmd


def conf_lines() -> list[str]:
    return [
        "listen_addresses = '127.0.0.1'",
        f"port = {config.PG_PORT}",
        "shared_buffers = 8GB",
        "effective_cache_size = 20GB",
        "work_mem = 32MB",
        "maintenance_work_mem = 1GB",
        "max_connections = 200",
        "wal_buffers = 64MB",
        "checkpoint_timeout = 15min",
        "max_wal_size = 8GB",
        "random_page_cost = 1.1",
        "track_io_timing = on",
        "log_min_duration_statement = 1000",
    ]


def _root(root: Path) -> Path:
    return Path(root)


def init_cluster(root: Path) -> None:
    data = _root(root) / "pgdata"
    if (data / "PG_VERSION").exists():
        return
    data.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(_as_odf([f"{PG_BIN}/initdb", "-D", str(data), "-U", "odf",
                            "--auth=trust", "--encoding=UTF8",
                            "--locale=C"]), check=True)
    with open(data / "postgresql.conf", "a", encoding="utf-8") as f:
        f.write("\n".join(conf_lines()) + "\n")
    hba = data / "pg_hba.conf"
    with open(hba, "a", encoding="utf-8") as f:
        f.write("host all all 127.0.0.1/32 trust\n")


def start(root: Path) -> None:
    data = _root(root) / "pgdata"
    status = subprocess.run(_as_odf([f"{PG_BIN}/pg_ctl", "-D", str(data),
                                     "status"]), capture_output=True)
    if status.returncode == 0:
        return
    subprocess.run(_as_odf([f"{PG_BIN}/pg_ctl", "-D", str(data), "-l",
                            str(_root(root) / "logs" / "postgres.log"),
                            "-w", "start"]), check=True)


def stop(root: Path) -> None:
    data = _root(root) / "pgdata"
    subprocess.run(_as_odf([f"{PG_BIN}/pg_ctl", "-D", str(data), "-m", "fast",
                            "-w", "stop"]), check=False)


def createdb(root: Path, name: str) -> None:
    subprocess.run([f"{PG_BIN}/createdb", "-h", "127.0.0.1",
                    "-p", str(config.PG_PORT), "-U", "odf", name], check=False)


def dsn(name: str) -> str:
    return f"postgresql+psycopg://odf@127.0.0.1:{config.PG_PORT}/{name}"
