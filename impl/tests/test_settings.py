from cryptography.fernet import Fernet
from odf.settings import Settings


def test_defaults():
    s = Settings(database_url="postgresql+psycopg://u:p@localhost/odf",
                 jwt_secret="x" * 32,
                 fernet_key=Fernet.generate_key().decode())
    assert s.query_timeout_s == 60
    assert s.query_max_rows == 10000
    assert s.aksk_time_window_s == 300
    assert s.db_pool_size + s.db_max_overflow >= 60
