import psycopg

SHOP = "shop"
MART = "mart"


def _pg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://")


DDL = [
    """CREATE TABLE IF NOT EXISTS customers (
        id bigint PRIMARY KEY, name text NOT NULL, phone text, email text,
        province text, city text, address text, register_at timestamptz,
        vip_level int, status text)""",
    """CREATE TABLE IF NOT EXISTS products (
        id bigint PRIMARY KEY, name text NOT NULL, category text,
        price numeric(12,2), cost numeric(12,2), status text,
        created_at timestamptz)""",
    """CREATE TABLE IF NOT EXISTS orders (
        id bigint PRIMARY KEY, customer_id bigint NOT NULL, order_no text,
        status text, channel text, province text, city text,
        amount numeric(12,2), discount numeric(12,2),
        created_at timestamptz, updated_at timestamptz)""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id bigint PRIMARY KEY, order_id bigint NOT NULL, product_id bigint,
        quantity int, unit_price numeric(12,2), amount numeric(12,2),
        discount numeric(12,2))""",
    """CREATE TABLE IF NOT EXISTS payments (
        id bigint PRIMARY KEY, order_id bigint NOT NULL, method text,
        amount numeric(12,2), status text, paid_at timestamptz,
        transaction_no text, failure_reason text)""",
    """CREATE TABLE IF NOT EXISTS refunds (
        id bigint PRIMARY KEY, order_id bigint, payment_id bigint,
        amount numeric(12,2), reason text, status text,
        created_at timestamptz)""",
    """CREATE TABLE IF NOT EXISTS events_raw (
        id bigint, event_id text, user_id bigint, session_id text,
        event_type text, page text, product_id bigint, ts timestamptz,
        properties jsonb, ip text, user_agent text) PARTITION BY RANGE (ts)""",
]


def _partitions() -> list[str]:
    lines = []
    for month in range(9, 13):
        start = f"2025-{month:02d}-01"
        end = "2026-01-01" if month == 12 else f"2025-{month + 1:02d}-01"
        lines.append(
            f"CREATE TABLE IF NOT EXISTS events_2025_{month:02d} "
            f"PARTITION OF events_raw FOR VALUES FROM ('{start}') TO ('{end}')")
    return lines


def create_schema(dsn: str) -> None:
    with psycopg.connect(_pg_dsn(dsn), autocommit=True) as conn:
        with conn.cursor() as cur:
            for statement in DDL + _partitions():
                cur.execute(statement)


def create_indexes(dsn: str) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_orders_customer ON orders (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_created ON orders (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_items_order ON order_items (order_id)",
        "CREATE INDEX IF NOT EXISTS ix_items_product ON order_items (product_id)",
        "CREATE INDEX IF NOT EXISTS ix_payments_order ON payments (order_id)",
        "CREATE INDEX IF NOT EXISTS ix_refunds_order ON refunds (order_id)",
        "CREATE INDEX IF NOT EXISTS ix_events_user_ts ON events_raw (user_id, ts)",
        "CREATE INDEX IF NOT EXISTS ix_events_event_id ON events_raw (event_id)",
    ]
    with psycopg.connect(_pg_dsn(dsn), autocommit=True) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)


ORDERS_COLUMNS = """(
    id bigint PRIMARY KEY, customer_id bigint NOT NULL, order_no text,
    status text, channel text, province text, city text,
    amount numeric(12,2), discount numeric(12,2),
    created_at timestamptz, updated_at timestamptz)"""


def create_mart(dsn: str, codes: list[str] | None = None) -> None:
    codes = codes or ["default"]
    statements = []
    for code in codes:
        for suffix in ("orders", "items"):
            statements.append(
                f"CREATE TABLE IF NOT EXISTS orders_clean_{code}_{suffix} "
                f"{ORDERS_COLUMNS}")
    with psycopg.connect(_pg_dsn(dsn), autocommit=True) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
