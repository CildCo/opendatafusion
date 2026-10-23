from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODF_", env_file=(".env", "/opt/odf/.env"))

    database_url: str
    jwt_secret: str
    fernet_key: str
    api_prefix: str = "/api/v1"
    query_timeout_s: int = 60
    query_max_rows: int = 10000
    metric_cache_ttl_s: int = 0
    metric_cache_size: int = 256
    preview_cache_ttl_s: int = 0
    preview_cache_size: int = 256
    dashboard_cache_ttl_s: int = 0
    dashboard_cache_size: int = 256
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout: int = 30
    db_pool_recycle_s: int = 1800
    aksk_time_window_s: int = 300
    aksk_allow_sha1: bool = True
    token_ttl_hours: int = 8
    password_min_length: int = 10
    password_require_classes: bool = True
    login_rate_per_min: int = 10
    totp_issuer: str = "OpenDataFusion"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_scopes: str = "openid profile email"
    oidc_auto_provision: bool = True
    ldap_url: str = ""
    ldap_user_dn_template: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_auto_provision: bool = True
    api_rate_default: int = 600
    metrics_enabled: bool = True
    log_json: bool = False
    otel_enabled: bool = False
    otel_endpoint: str = "http://127.0.0.1:4317"
    otel_service_name: str = "odf"
    otel_sample_ratio: float = 0.1
    file_backend: str = "local"
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = ""
    webhook_allow_private: bool = False
    webhook_max_payload: int = 65536
    http_allow_private: bool = False
    http_allowed_hosts: str = ""
    http_timeout_s: int = 30
    http_max_response_mb: int = 10
    audit_retention_days: int = 0
    file_dir: str = "./data/files"
    file_max_mb: int = 20
    file_source_roots: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
