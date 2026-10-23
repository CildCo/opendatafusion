import psycopg


def _pg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://")


def table_count(dsn: str, table: str) -> int:
    with psycopg.connect(_pg_dsn(dsn)) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from {table}")
            return int(cur.fetchone()[0])


def compare_counts(expected: dict, actual: dict) -> list[str]:
    errors = []
    for key, value in expected.items():
        if actual.get(key) != value:
            errors.append(f"{key}: {value} != {actual.get(key)}")
    return errors


def compare_checksums(expected: list, actual: list) -> list[str]:
    if expected == actual:
        return []
    return [f"checksum mismatch: {expected} != {actual}"]


def cursor_ok(actual: str | None, expected: str) -> bool:
    return str(actual) == str(expected)


def tenant_isolation(client) -> dict:
    checks = {}
    for path in ("/datasets", "/pipelines", "/apis", "/quality/rules"):
        try:
            rows = client.get(path)
            checks[path] = len(rows)
        except Exception:
            checks[path] = "denied"
    return checks
