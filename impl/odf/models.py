from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, ForeignKey,
                        Index, Integer, JSON, String, Text, UniqueConstraint,
                        text)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# SQLite only autoincrements INTEGER PRIMARY KEY; keep BIGINT on PostgreSQL.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


def now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[int] = mapped_column(Integer, default=1)
    environment: Mapped[str] = mapped_column(String(16), default="dev")
    quota_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(
        String(512), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oidc_sub: Mapped[str | None] = mapped_column(String(255), unique=True,
                                                nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectMember(Base):
    __tablename__ = "project_member"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer")


class Datasource(Base):
    __tablename__ = "datasource"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    dsn_encrypted: Mapped[str] = mapped_column(Text)
    auto_sync_minutes: Mapped[int] = mapped_column(Integer, default=0)
    limit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DatasourceHealth(Base):
    __tablename__ = "datasource_health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datasource_id: Mapped[int] = mapped_column(
        ForeignKey("datasource.id"), index=True)
    action: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now,
                                         index=True)


class Dataset(Base):
    __tablename__ = "dataset"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"), index=True)
    schema_name: Mapped[str] = mapped_column(String(128))
    table_name: Mapped[str] = mapped_column(String(128))
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                 index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64), default="")


class Column(Base):
    __tablename__ = "dataset_column"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")


class AkSk(Base):
    __tablename__ = "ak_sk"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    ak: Mapped[str] = mapped_column(String(64), unique=True)
    sk_encrypted: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ip_allowlist: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer,
                                                            nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))


class DatasetTag(Base):
    __tablename__ = "dataset_tag"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), index=True)


class QualityRule(Base):
    __tablename__ = "quality_rule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    column_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    alert_on_fail: Mapped[bool] = mapped_column(Boolean, default=False)


class QualityResult(Base):
    __tablename__ = "quality_result"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("quality_rule.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Standard(Base):
    __tablename__ = "data_standard"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")


class StandardMapping(Base):
    __tablename__ = "standard_mapping"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("data_standard.id"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"), index=True)
    column_name: Mapped[str] = mapped_column(String(128))


class AlertRule(Base):
    __tablename__ = "alert_rule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alert"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rule.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True,
                                                    index=True)
    acked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AlertNote(Base):
    __tablename__ = "alert_note"
    __table_args__ = (Index("ix_alert_note_alert_created", "alert_id",
                            "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    alert_id: Mapped[int] = mapped_column(BigInteger,
                                          ForeignKey("alert.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="info")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)


class NotificationRead(Base):
    __tablename__ = "notification_read"
    __table_args__ = (UniqueConstraint("user_id", "notification_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"),
                                         index=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notification.id"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                              default=now)


class Domain(Base):
    __tablename__ = "domain"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class GlossaryTerm(Base):
    __tablename__ = "glossary_term"
    __table_args__ = (UniqueConstraint("project_id", "term"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                 index=True)
    term: Mapped[str] = mapped_column(String(128))
    definition: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class CatalogComment(Base):
    __tablename__ = "catalog_comment"
    __table_args__ = (Index("ix_catalog_comment_dataset_created",
                            "dataset_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"),
                                            index=True)
    actor: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64),
                                                    nullable=True)


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (UniqueConstraint("project_id", "user_id", "object_type",
                                       "object_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"),
                                         index=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)


class SavedQuery(Base):
    __tablename__ = "saved_query"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"),
                                          index=True)
    name: Mapped[str] = mapped_column(String(128))
    tab: Mapped[str] = mapped_column(String(16), default="single")
    datasource_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasource.id"), nullable=True)
    sql_text: Mapped[str] = mapped_column(Text, default="")
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    row_limit: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class QueryRun(Base):
    __tablename__ = "query_run"
    __table_args__ = (Index("ix_query_run_project_created",
                            "project_id", "created_at"),
                      Index("ix_query_run_datasource_created",
                            "datasource_id", "created_at"))
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True,
                                    autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    datasource_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasource.id"), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(16), default="workbench")
    status: Mapped[str] = mapped_column(String(8), default="ok")
    sql_hash: Mapped[str] = mapped_column(String(64), default="")
    sql_preview: Mapped[str] = mapped_column(Text, default="")
    sql_text: Mapped[str] = mapped_column(Text, default="")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)


class ContractCheck(Base):
    __tablename__ = "contract_check"
    __table_args__ = (Index("ix_contract_check_asset_checked",
                            "asset_id", "checked_at"),)
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True,
                                    autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    issues_json: Mapped[list] = mapped_column(JSON, default=list)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, index=True)


class ColumnPolicy(Base):
    __tablename__ = "column_policy"
    __table_args__ = (UniqueConstraint("datasource_id", "schema_name",
                                       "table_name", "column_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"),
                                               index=True)
    schema_name: Mapped[str] = mapped_column(String(128), default="")
    table_name: Mapped[str] = mapped_column(String(128))
    column_name: Mapped[str] = mapped_column(String(128))
    classification: Mapped[str] = mapped_column(String(32), default="pii")
    mask_type: Mapped[str] = mapped_column(String(32), default="redact")
    exempt_roles_json: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class ColumnTerm(Base):
    __tablename__ = "column_term"
    __table_args__ = (UniqueConstraint("dataset_id", "column_name", "term_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"),
                                            index=True)
    column_name: Mapped[str] = mapped_column(String(128))
    term_id: Mapped[int] = mapped_column(ForeignKey("glossary_term.id"),
                                         index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class RowPolicy(Base):
    __tablename__ = "row_policy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    column: Mapped[str] = mapped_column(String(128))
    op: Mapped[str] = mapped_column(String(16))
    value: Mapped[object] = mapped_column(JSON)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class ApiRate(Base):
    __tablename__ = "api_rate"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)


class ApiCallStat(Base):
    __tablename__ = "api_call_stat"
    __table_args__ = (UniqueConstraint("day", "api_id", "ak"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[object] = mapped_column(Date, index=True)
    api_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    ak: Mapped[str] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscription"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024))
    secret_encrypted: Mapped[str] = mapped_column(String(512))
    events_json: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"
    __table_args__ = (Index("ix_webhook_delivery_status_next", "status",
                            "next_attempt_at"),)
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True,
                                    autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("webhook_subscription.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    event: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending",
                                        index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class FileObject(Base):
    __tablename__ = "file_object"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class PortalSetting(Base):
    __tablename__ = "portal_setting"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            unique=True, index=True)
    brand_name: Mapped[str] = mapped_column(String(64),
                                            default="OpenDataFusion")
    primary_color: Mapped[str] = mapped_column(String(16), default="#1d4ed8")
    welcome_title: Mapped[str] = mapped_column(String(128), default="")
    welcome_text: Mapped[str] = mapped_column(String(1000), default="")
    hidden_menus: Mapped[list] = mapped_column(JSON, default=list)
    allowed_menus: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, onupdate=now)


class PlatformSetting(Base):
    __tablename__ = "platform_setting"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, onupdate=now)


class AssetGrant(Base):
    __tablename__ = "asset_grant"
    __table_args__ = (
        Index("ux_asset_grant_active", "asset_id", "grantee_project_id",
              unique=True,
              sqlite_where=text("revoked_at IS NULL"),
              postgresql_where=text("revoked_at IS NULL")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="api")
    owner_project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), index=True)
    grantee_project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), index=True)
    granted_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class AssetRequest(Base):
    __tablename__ = "asset_request"
    __table_args__ = (
        Index("ux_asset_request_pending", "asset_id", "grantee_project_id",
              unique=True,
              sqlite_where=text("status = 'pending'"),
              postgresql_where=text("status = 'pending'")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="api")
    owner_project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), index=True)
    grantee_project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), index=True)
    requested_by: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class ShareLink(Base):
    __tablename__ = "share_link"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="share")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportSchedule(Base):
    __tablename__ = "report_schedule"
    __table_args__ = (UniqueConstraint("asset_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    cron: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64))
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class ChangeRequest(Base):
    __tablename__ = "change_request"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_run_at", "status", "run_at"),)
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset.id"), nullable=True)
    asset_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LakehouseMaintenance(Base):
    __tablename__ = "lakehouse_maintenance"
    __table_args__ = (UniqueConstraint("project_id", "datasource_id",
                                       "schema_name", "table_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    datasource_id: Mapped[int] = mapped_column(
        ForeignKey("datasource.id"), index=True)
    schema_name: Mapped[str] = mapped_column(String(128))
    table_name: Mapped[str] = mapped_column(String(128), default="")
    cron: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    optimize: Mapped[bool] = mapped_column(Boolean, default=True)
    expire_snapshots: Mapped[bool] = mapped_column(Boolean, default=True)
    retention: Mapped[str] = mapped_column(String(16), default="7d")
    file_size_threshold: Mapped[str] = mapped_column(String(16),
                                                     default="128MB")
    created_by: Mapped[str] = mapped_column(String(64))
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)


class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64))
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                 index=True)
    contract_json: Mapped[dict] = mapped_column(JSON, default=dict)
    cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    retry_backoff_seconds: Mapped[int] = mapped_column(Integer, default=30)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    max_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    certification: Mapped[str] = mapped_column(String(16), default="none",
                                               index=True)
    certified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(16), default="active",
                                           index=True)
    lifecycle_note: Mapped[str] = mapped_column(Text, default="")
    lifecycle_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    draft_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cursor_json: Mapped[dict | None] = mapped_column(JSON, default=dict,
                                                     nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, onupdate=now)

    def __init__(self, **kw):
        kw.setdefault("enabled", True)
        super().__init__(**kw)


class AssetVersion(Base):
    __tablename__ = "asset_version"
    __table_args__ = (UniqueConstraint("asset_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LineageEdge(Base):
    __tablename__ = "lineage_edge"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                index=True)
    from_type: Mapped[str] = mapped_column(String(32))
    from_id: Mapped[str] = mapped_column(String(128))
    from_ref: Mapped[str] = mapped_column(String(256))
    from_column: Mapped[str | None] = mapped_column(String(256),
                                                    nullable=True)
    to_type: Mapped[str] = mapped_column(String(32))
    to_id: Mapped[str] = mapped_column(String(128))
    to_ref: Mapped[str] = mapped_column(String(256))
    to_column: Mapped[str | None] = mapped_column(String(256),
                                                  nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PipelineNodeRun(Base):
    __tablename__ = "pipeline_node_run"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    in_num: Mapped[int] = mapped_column(BigInteger, default=0)
    out_num: Mapped[int] = mapped_column(BigInteger, default=0)
    ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EngineJob(Base):
    __tablename__ = "engine_job"
    __table_args__ = (Index("ix_engine_job_status_synced", "status",
                            "synced_at"),)
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True,
                                    autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"),
                                                 nullable=True, index=True)
    engine: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(63), unique=True)
    spec_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending",
                                        index=True)
    external_id: Mapped[str] = mapped_column(String(255), default="")
    submitted_by: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sync_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class CdcSource(Base):
    __tablename__ = "cdc_source"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    name: Mapped[str] = mapped_column(String(128))
    connector_name: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    password_encrypted: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now, onupdate=now)


class JobDependency(Base):
    __tablename__ = "job_dependency"
    __table_args__ = (UniqueConstraint("project_id", "downstream_type",
                                       "downstream_id", "upstream_type",
                                       "upstream_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"),
                                            index=True)
    downstream_type: Mapped[str] = mapped_column(String(16))
    downstream_id: Mapped[int] = mapped_column(Integer)
    upstream_type: Mapped[str] = mapped_column(String(16))
    upstream_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=now)

