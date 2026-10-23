import json
from datetime import date, datetime

from sqlalchemy import MetaData, Table, and_, create_engine, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from odf.connectors.base import Sink, Source
from odf.services.datasource import connect_args_for, get_dsn


def _coerce(column, value):
    if value is None:
        return None
    try:
        py = column.type.python_type
    except Exception:
        return value
    try:
        if py is int:
            return int(value)
        if py is float:
            return float(value)
        if py is datetime:
            return datetime.fromisoformat(value)
        if py is date:
            return date.fromisoformat(value)
        if py is bool:
            return str(value).lower() in ("1", "true", "t", "yes")
    except Exception:
        return value
    return value


def engine_for(ds):
    dsn = get_dsn(ds)
    return create_engine(dsn, connect_args=connect_args_for(ds.kind, dsn))


def table_for(name, engine):
    if "." in name:
        schema, table = name.split(".", 1)
        return Table(table, MetaData(), schema=schema, autoload_with=engine)
    return Table(name, MetaData(), autoload_with=engine)


def parse_cursor(value):
    if not value:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [value, None]
    except Exception:
        return [value, None]


def format_cursor(col_value, pk_value) -> str:
    return json.dumps([str(col_value), str(pk_value)], ensure_ascii=False)


def insert_for(dialect):
    if dialect == "postgresql":
        return pg_insert
    if dialect == "sqlite":
        return sqlite_insert
    if dialect in ("mysql", "mariadb"):
        return mysql_insert
    raise ValueError("unsupported sink dialect: %s" % dialect)


class SQLSource(Source):
    def __init__(self, ds, dag):
        self.ds, self.dag = ds, dag

    def read(self, cursor, limit):
        engine = engine_for(self.ds)
        st = table_for(self.dag["source_table"], engine)
        col = self.dag.get("cursor_column")
        pk = self.dag["pk"]
        q = select(st)
        cur = parse_cursor(cursor)
        if col and cur:
            c_val = _coerce(st.c[col], cur[0])
            p_val = _coerce(st.c[pk], cur[1]) if len(cur) > 1 else None
            if p_val is None:
                q = q.where(st.c[col] > c_val)
            else:
                q = q.where(or_(st.c[col] > c_val,
                                and_(st.c[col] == c_val, st.c[pk] > p_val)))
        if col:
            q = q.order_by(st.c[col], st.c[pk])
        q = q.limit(limit)
        with engine.connect() as c:
            rows = [dict(r) for r in c.execute(q).mappings().all()]
        new_cursor = cursor
        if col and rows:
            new_cursor = format_cursor(rows[-1][col], rows[-1][pk])
        return rows, new_cursor


class SQLSink(Sink):
    def __init__(self, ds, dag):
        self.ds, self.dag = ds, dag

    def write(self, rows):
        engine = engine_for(self.ds)
        tt = table_for(self.dag["sink_table"], engine)
        pk = self.dag.get("pk") or ["id"]
        if not isinstance(pk, list):
            pk = [pk]
        mode = self.dag.get("mode") or "upsert"
        if mode not in ("upsert", "append"):
            raise ValueError("unsupported sink mode: %s" % mode)
        dialect = engine.dialect.name
        insert = insert_for(dialect)
        groups = {}
        for row in rows:
            vals = {k: v for k, v in row.items() if k in tt.c}
            groups.setdefault(tuple(sorted(vals)), []).append(vals)
        with engine.begin() as c:
            for key, payload in groups.items():
                if not key:
                    for _ in payload:
                        c.execute(insert(tt))
                    continue
                stmt = insert(tt)
                if mode == "append":
                    c.execute(stmt, payload)
                    continue
                if dialect in ("mysql", "mariadb"):
                    update = {k: getattr(stmt.inserted, k)
                              for k in key if k not in pk}
                    if update:
                        stmt = stmt.on_duplicate_key_update(**update)
                    else:
                        stmt = stmt.on_duplicate_key_update({
                            pk[0]: getattr(stmt.inserted, pk[0])})
                else:
                    update = {k: stmt.excluded[k]
                              for k in key if k not in pk}
                    if update:
                        stmt = stmt.on_conflict_do_update(
                            index_elements=pk, set_=update)
                    else:
                        stmt = stmt.on_conflict_do_nothing(index_elements=pk)
                c.execute(stmt, payload)
        return len(rows)
