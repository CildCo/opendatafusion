import re

from odf.models import PortalSetting
from odf.services.audit import write_audit

MENUS = {"/dashboard", "/ops", "/datasources", "/catalog", "/workbench",
         "/pipelines", "/flows", "/apis", "/tools", "/datasets",
         "/dashboards", "/apps", "/quality", "/alerts", "/changes",
         "/grants", "/webhooks", "/files", "/workspace", "/security",
         "/users", "/audit"}
DEFAULTS = {"brand_name": "OpenDataFusion", "primary_color": "#1d4ed8",
            "welcome_title": "", "welcome_text": "", "hidden_menus": [],
            "allowed_menus": None}
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _out(row):
    if not row:
        return dict(DEFAULTS)
    return {"brand_name": row.brand_name,
            "primary_color": row.primary_color,
            "welcome_title": row.welcome_title,
            "welcome_text": row.welcome_text,
            "hidden_menus": row.hidden_menus or [],
            "allowed_menus": row.allowed_menus}


def get_portal(session, project_id):
    return _out(session.query(PortalSetting)
                .filter_by(project_id=project_id).first())


def _validate(fields):
    if "brand_name" in fields:
        name = fields["brand_name"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
            raise ValueError("invalid brand name")
        fields = {**fields, "brand_name": name.strip()}
    if "primary_color" in fields:
        color = fields["primary_color"]
        if not isinstance(color, str) or not _COLOR.fullmatch(color):
            raise ValueError("invalid primary color")
    if "welcome_title" in fields:
        value = fields["welcome_title"]
        if not isinstance(value, str) or len(value) > 128:
            raise ValueError("invalid welcome title")
    if "welcome_text" in fields:
        value = fields["welcome_text"]
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError("invalid welcome text")
    if "hidden_menus" in fields:
        menus = fields["hidden_menus"]
        if not isinstance(menus, list) or \
                any(not isinstance(m, str) or m not in MENUS for m in menus):
            raise ValueError("invalid hidden menus")
        if len(set(menus)) != len(menus):
            raise ValueError("duplicate hidden menus")


def update_portal(session, project_id, fields, actor):
    _validate(fields)
    row = (session.query(PortalSetting)
           .filter_by(project_id=project_id).first())
    if not row:
        row = PortalSetting(project_id=project_id,
                            **{**DEFAULTS, "hidden_menus": []})
        session.add(row)
    for key in ("brand_name", "primary_color", "welcome_title",
                "welcome_text"):
        if key in fields:
            setattr(row, key, fields[key].strip()
                    if key == "brand_name" else fields[key])
    if "hidden_menus" in fields:
        row.hidden_menus = fields["hidden_menus"]
    if "allowed_menus" in fields:
        row.allowed_menus = fields["allowed_menus"]
    row.updated_by = actor
    session.commit()
    write_audit(session, actor, "update_portal", str(project_id), {})
    return _out(row)
