import sqlite3
from pathlib import Path


def build(root: Path, rows: int = 5_000_000) -> Path:
    db = Path(root) / "edge.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE stores (id INTEGER PRIMARY KEY, name TEXT, city TEXT)")
    con.execute("CREATE TABLE inventory (store_id INTEGER, product_id INTEGER, qty INTEGER)")
    con.execute("CREATE TABLE local_orders (id INTEGER PRIMARY KEY, store_id INTEGER, amount REAL, created_at TEXT)")
    con.executemany("INSERT INTO stores VALUES (?,?,?)",
                    [(i, f"门店{i}", ["北京", "上海", "广州", "深圳"][i % 4])
                     for i in range(1, 1001)])
    con.executemany("INSERT INTO inventory VALUES (?,?,?)",
                    [(i % 1000 + 1, i % 400000 + 1, (i * 7) % 100)
                     for i in range(1, 1_000_001)])
    con.executemany(
        "INSERT INTO local_orders VALUES (?,?,?,?)",
        [(i, i % 1000 + 1, round((i * 37) % 1000 + 0.5, 2),
          f"2025-{i % 12 + 1:02d}-{i % 28 + 1:02d}T10:00:00")
         for i in range(1, rows + 1)])
    con.commit()
    con.close()
    return db
