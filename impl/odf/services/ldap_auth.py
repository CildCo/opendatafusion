from odf.settings import get_settings


def authenticate_ldap(username, password):
    s = get_settings()
    if not s.ldap_url or not s.ldap_user_dn_template:
        return None
    if not password:
        return None
    try:
        from ldap3 import Connection, Server
    except ImportError:
        raise RuntimeError("ldap3 is not installed")
    user_dn = s.ldap_user_dn_template.format(username=username)
    server = Server(s.ldap_url)
    conn = Connection(server, user=user_dn, password=password,
                      auto_bind=True)
    try:
        return username
    finally:
        conn.unbind()
