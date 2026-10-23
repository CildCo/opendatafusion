from cryptography.fernet import Fernet

from odf.settings import get_settings


def encrypt_secret(s: str) -> str:
    return Fernet(get_settings().fernet_key.encode()).encrypt(s.encode()).decode()


def decrypt_secret(s: str) -> str:
    return Fernet(get_settings().fernet_key.encode()).decrypt(s.encode()).decode()
