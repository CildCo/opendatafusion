import os
import secrets
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet

from bench import config, pg, stack


def build_env_text(control_dsn: str, shop_dsn: str, mart_dsn: str,
                   jwt_secret: str, fernet_key: str) -> str:
    return "\n".join(stack.env_lines(
        control_dsn, shop_dsn, mart_dsn, jwt_secret, fernet_key)) + "\n"


def _chown(path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        subprocess.run(["chown", "-R", "odf:odf", str(path)], check=True)


def _start_aux(root: Path) -> None:
    for name, module in (("mock_http", "bench.generate.mock_http"),
                         ("proxy", "bench.faults.proxy")):
        log = open(root / "logs" / f"{name}.log", "ab")
        proc = subprocess.Popen(
            [stack.PYTHON, "-m", module],
            cwd=str(root), stdout=log, stderr=log, start_new_session=True,
            env={**os.environ, "PYTHONPATH": str(root)})
        (root / f"{name}.pid").write_text(str(proc.pid))


def _migrate(root: Path, env_file: Path) -> None:
    command = (
        f"set -a && . {env_file} && set +a && cd {root}/app && "
        f"{stack.PYTHON} -m alembic upgrade head")
    subprocess.run(command, shell=True, check=True)


def main() -> int:
    root = config.ROOT
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / config.MARKER).write_text("odf-bench\n", encoding="utf-8")
    (root / "files").mkdir(parents=True, exist_ok=True)
    (root / "report").mkdir(parents=True, exist_ok=True)
    stack.copy_app(dst=root / "app")
    _chown(root)
    pg.init_cluster(root)
    pg.start(root)
    for db in (config.DB_CONTROL, config.DB_SHOP, config.DB_MART):
        pg.createdb(root, db)
    text = build_env_text(
        pg.dsn(config.DB_CONTROL),
        pg.dsn(config.DB_SHOP).replace(
            f":{config.PG_PORT}", f":{config.PROXY_PORT}"),
        pg.dsn(config.DB_MART).replace(
            f":{config.PG_PORT}", f":{config.PROXY_PORT}"),
        secrets.token_urlsafe(48), Fernet.generate_key().decode())
    (root / "env").write_text(text, encoding="utf-8")
    (root / "env").chmod(0o600)
    _chown(root / "env")
    _migrate(root, root / "env")
    _start_aux(root)
    stack.start(root, root / "app", root / "env")
    if not stack.wait_ready(90):
        raise SystemExit("bench API did not become ready")
    stack.seed_admin(root / "env")
    print("SETUP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
