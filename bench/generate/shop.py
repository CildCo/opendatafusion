from pathlib import Path

import duckdb

ROW_COUNTS = {
    "customers": 1_500_000,
    "products": 400_000,
    "orders": 15_000_000,
    "order_items": 50_000_000,
    "payments": 15_000_000,
    "refunds": 1_500_000,
    "events": 30_000_000,
}


def parquet_path(root: Path, table: str) -> Path:
    return root / "parquet" / "shop" / f"{table}.parquet"


def _count(table: str, scale: float) -> int:
    return max(1, round(ROW_COUNTS[table] * scale))


def _p(root: Path, table: str) -> str:
    return parquet_path(root, table).as_posix()


def generate(root: Path, scale: float = 1.0) -> dict[str, Path]:
    root = Path(root)
    (root / "parquet" / "shop").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='6GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SELECT setseed(0.20261022)")

    con.execute("CREATE TABLE dim_name(idx INTEGER, name VARCHAR)")
    con.executemany("INSERT INTO dim_name VALUES (?, ?)",
                    [(i, n) for i, n in enumerate(
                        ["赵伟", "钱芳", "孙娜", "李敏", "周静", "吴丽",
                         "郑强", "王磊", "冯军", "陈洋", "褚勇", "卫艳",
                         "蒋杰", "沈娟", "韩涛", "杨明", "朱超", "秦秀英",
                         "尤霞", "许平"] * 50)])
    con.execute("CREATE TABLE dim_city(idx INTEGER, city VARCHAR, province VARCHAR)")
    con.executemany("INSERT INTO dim_city VALUES (?, ?, ?)",
                    [(i, c, p) for i, (c, p) in enumerate(zip(
                        ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都",
                         "武汉", "西安", "苏州", "天津", "重庆", "长沙", "郑州",
                         "青岛", "宁波"] * 20,
                        ["北京市", "上海市", "广东省", "广东省", "浙江省",
                         "江苏省", "四川省", "湖北省", "陕西省", "江苏省",
                         "天津市", "重庆市", "湖南省", "河南省", "山东省",
                         "浙江省"] * 20))])
    con.execute("CREATE TABLE dim_product(idx INTEGER, name VARCHAR, category VARCHAR)")
    con.executemany("INSERT INTO dim_product VALUES (?, ?, ?)",
                    [(i, f"{b}{c}{w}", c) for i, (b, c, w) in enumerate(
                        [(b, c, w) for b in ["华光", "山海", "云启", "青禾",
                                             "星河", "远山", "长风", "万象"]
                         for c in ["手机数码", "家用电器", "服饰鞋包", "美妆个护",
                                   "食品生鲜", "母婴玩具", "运动户外", "家居家装"]
                         for w in ["旗舰版", "轻量款", "家庭装", "经典款",
                                   "升级版", "便携款", "礼盒装", "专业版"]])])

    n = _count("customers", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, n.name AS name,
            '1' || lpad((((i*7919)%900000000)+100000000)::text, 9, '0') AS phone,
            'user' || i || '@example.cn' AS email,
            c.province AS province, c.city AS city,
            c.province || c.city || '某路' || ((i*37)%200+1) || '号' AS address,
            TIMESTAMP '2023-01-01' + ((i*104729)%63072000) * INTERVAL 1 SECOND AS register_at,
            ((i*13)%6+1) AS vip_level,
            CASE WHEN i%997=0 THEN 'disabled' ELSE 'active' END AS status
          FROM range(1, {n+1}) t(i)
          JOIN dim_name n ON n.idx=(i*7919)%(SELECT count(*) FROM dim_name)
          JOIN dim_city c ON c.idx=(i*104729)%(SELECT count(*) FROM dim_city)
        ) TO '{_p(root, 'customers')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("products", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, p.name AS name, p.category AS category,
            round((20 + (i*37)%5000 + (i%100)/100.0)::numeric, 2) AS price,
            round((10 + (i*29)%3000)::numeric, 2) AS cost,
            CASE WHEN i%211=0 THEN 'offline' ELSE 'online' END AS status,
            TIMESTAMP '2023-01-01' + ((i*7919)%63072000) * INTERVAL 1 SECOND AS created_at
          FROM range(1, {n+1}) t(i)
          JOIN dim_product p ON p.idx=(i*7919)%(SELECT count(*) FROM dim_product)
        ) TO '{_p(root, 'products')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("orders", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, ((i*7919)%{_count('customers', scale)})+1 AS customer_id,
            'SO' || lpad(i::text, 12, '0') AS order_no,
            CASE WHEN i%50=0 THEN 'cancelled' WHEN i%17=0 THEN 'refunded'
                 WHEN i%7=0 THEN 'paid' ELSE 'completed' END AS status,
            CASE WHEN i%3=0 THEN 'app' WHEN i%3=1 THEN 'web' ELSE 'mini' END AS channel,
            c.province AS province, c.city AS city,
            round((10 + (i*37)%990 + (i%100)/100.0)::numeric, 2) AS amount,
            round(((i*37)%50)::numeric, 2) AS discount,
            TIMESTAMP '2025-01-01' + ((i*104729)%31536000) * INTERVAL 1 SECOND AS created_at,
            TIMESTAMP '2025-01-01' + ((i*104729)%31536000 + (i%3600)) * INTERVAL 1 SECOND AS updated_at
          FROM range(1, {n+1}) t(i)
          JOIN dim_city c ON c.idx=(i*7919)%(SELECT count(*) FROM dim_city)
        ) TO '{_p(root, 'orders')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("order_items", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, ((i*7919)%{_count('orders', scale)})+1 AS order_id,
            ((i*104729)%{_count('products', scale)})+1 AS product_id,
            ((i*13)%5+1) AS quantity,
            round((10 + (i*37)%900 + (i%100)/100.0)::numeric, 2) AS unit_price,
            round((((i*13)%5+1) * (10 + (i*37)%900 + (i%100)/100.0))::numeric, 2) AS amount,
            round(((i*29)%30)::numeric, 2) AS discount
          FROM range(1, {n+1}) t(i)
        ) TO '{_p(root, 'order_items')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("payments", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, ((i*7919)%{_count('orders', scale)})+1 AS order_id,
            CASE WHEN i%4=0 THEN 'alipay' WHEN i%4=1 THEN 'wechat'
                 WHEN i%4=2 THEN 'card' ELSE 'balance' END AS method,
            round((10 + (i*37)%900 + (i%100)/100.0)::numeric, 2) AS amount,
            CASE WHEN i%23=0 THEN 'failed' ELSE 'success' END AS status,
            TIMESTAMP '2025-01-01' + ((i*104729)%31536000) * INTERVAL 1 SECOND AS paid_at,
            'TX' || lpad(i::text, 14, '0') AS transaction_no,
            CASE WHEN i%23=0 THEN 'insufficient funds' ELSE NULL END AS failure_reason
          FROM range(1, {n+1}) t(i)
        ) TO '{_p(root, 'payments')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("refunds", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, ((i*7919)%{_count('orders', scale)})+1 AS order_id,
            ((i*104729)%{_count('payments', scale)})+1 AS payment_id,
            round((10 + (i*37)%300 + (i%100)/100.0)::numeric, 2) AS amount,
            CASE WHEN i%5=0 THEN '质量问题' WHEN i%5=1 THEN '七天无理由'
                 WHEN i%5=2 THEN '发错货' ELSE '其他' END AS reason,
            CASE WHEN i%11=0 THEN 'rejected' ELSE 'approved' END AS status,
            TIMESTAMP '2025-01-01' + ((i*104729)%31536000) * INTERVAL 1 SECOND AS created_at
          FROM range(1, {n+1}) t(i)
        ) TO '{_p(root, 'refunds')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = _count("events", scale)
    con.execute(f"""
        COPY (
          SELECT i AS id, 'evt_' || md5(i::text) AS event_id,
            ((i*7919)%{_count('customers', scale)})+1 AS user_id,
            'sess_' || ((i/20)::bigint) AS session_id,
            CASE WHEN i%5=0 THEN 'view' WHEN i%5=1 THEN 'click'
                 WHEN i%5=2 THEN 'add_cart' WHEN i%5=3 THEN 'pay' ELSE 'search' END AS event_type,
            '/p/' || ((i*37)%{_count('products', scale)}+1) AS page,
            ((i*37)%{_count('products', scale)})+1 AS product_id,
            TIMESTAMP '2025-09-01' + ((i*104729)%2592000) * INTERVAL 1 SECOND AS ts,
            json_object('source', CASE WHEN i%3=0 THEN 'app' ELSE 'web' END,
                        'price', (i%1000)) AS properties,
            '10.' || (i%255) || '.' || (i%255) || '.' || (i%255) AS ip,
            'Mozilla/5.0' AS user_agent
          FROM range(1, {n+1}) t(i)
        ) TO '{_p(root, 'events')}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    return {table: parquet_path(root, table) for table in ROW_COUNTS}
