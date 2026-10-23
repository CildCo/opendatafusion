from odf.settings import get_settings

COMMON = {"password", "password1", "12345678", "123456789", "qwerty123",
          "admin123", "letmein123", "welcome123", "iloveyou"}


def validate_password(password):
    s = get_settings()
    if not isinstance(password, str) or len(password) < s.password_min_length:
        raise ValueError("password must be at least %d characters"
                         % s.password_min_length)
    if password.lower() in COMMON:
        raise ValueError("password is too common")
    if s.password_require_classes:
        classes = (any(c.isupper() for c in password),
                   any(c.islower() for c in password),
                   any(c.isdigit() for c in password),
                   any(not c.isalnum() for c in password))
        if not all(classes):
            raise ValueError("password must include upper, lower, digit and "
                             "symbol characters")
    return True
