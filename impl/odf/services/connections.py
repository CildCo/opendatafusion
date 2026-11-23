from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from odf.services.datasource import connect_args_for, get_dsn

SQL_KINDS = ("postgres", "postgresql", "mysql", "mariadb", "oracle",
             "mssql", "sqlserver", "tidb", "doris", "starrocks",
             "oceanbase", "opengauss", "kingbase", "gaussdb", "sqlite")
SSH_KEYS = ("ssh_host", "ssh_port", "ssh_user", "ssh_password")


@contextmanager
def engine_for_dsn(dsn, kind=""):
    url = make_url(dsn)
    query = dict(url.query)
    tunnel = None
    host = query.pop("ssh_host", None)
    port = int(query.pop("ssh_port", 22) or 22)
    user = query.pop("ssh_user", None)
    password = query.pop("ssh_password", None)
    if host:
        from sshtunnel import SSHTunnelForwarder
        target_port = url.port or {"postgresql": 5432, "mysql": 3306,
                                   "oracle": 1521, "mssql": 1433}.get(
                                       url.get_backend_name(), 5432)
        tunnel = SSHTunnelForwarder(
            (host, port), ssh_username=user, ssh_password=password,
            remote_bind_address=(url.host or "127.0.0.1", target_port))
        tunnel.start()
        url = url.set(host="127.0.0.1", port=tunnel.local_bind_port,
                      query=query)
    else:
        url = url.set(query=query)
    engine = create_engine(str(url),
                           connect_args=connect_args_for(kind, str(url)))
    try:
        yield engine
    finally:
        engine.dispose()
        if tunnel is not None:
            tunnel.stop()


@contextmanager
def engine_for(ds):
    with engine_for_dsn(get_dsn(ds), ds.kind) as engine:
        yield engine
