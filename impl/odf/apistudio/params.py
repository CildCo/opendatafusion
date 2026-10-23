import re
from datetime import date, datetime

PARAM_TYPES = {"string", "number", "date", "bool"}
MAX_IN_VALUES = 100
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ParamError(ValueError):
    def __init__(self, message, parameter=None):
        super().__init__(message)
        self.parameter = parameter


def validate_param_defs(defs):
    out, seen = [], set()
    for p in defs or []:
        if not isinstance(p, dict):
            raise ParamError("parameter definition must be an object")
        name = p.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ParamError("invalid parameter name: %s" % name, name)
        if name in seen:
            raise ParamError("duplicate parameter: %s" % name, name)
        seen.add(name)
        typ = p.get("type", "string")
        if typ not in PARAM_TYPES:
            raise ParamError("unsupported parameter type: %s" % typ, name)
        out.append({"name": name, "type": typ,
                    "required": bool(p.get("required")),
                    "default": p.get("default"),
                    "example": p.get("example")})
    return out


def _coerce_value(p, value):
    typ = p["type"]
    if value is None:
        return None
    if isinstance(value, list):
        if len(value) > MAX_IN_VALUES:
            raise ParamError("too many values for parameter %s" % p["name"],
                             p["name"])
        return [_coerce_value({**p, "name": p["name"]}, v) for v in value]
    if typ == "string":
        return str(value)
    if typ == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ParamError("parameter %s must be a number" % p["name"],
                             p["name"])
        return int(number) if number.is_integer() else number
    if typ == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("1", "true", "t", "yes", "y"):
            return True
        if text in ("0", "false", "f", "no", "n"):
            return False
        raise ParamError("parameter %s must be a boolean" % p["name"],
                         p["name"])
    if typ == "date":
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        text = str(value)
        try:
            if "T" in text or " " in text:
                datetime.fromisoformat(text)
            else:
                date.fromisoformat(text)
        except ValueError:
            raise ParamError("parameter %s must be an ISO date" % p["name"],
                             p["name"])
        return text
    raise ParamError("unsupported parameter type: %s" % typ, p["name"])


def coerce_params(defs, values):
    values = values or {}
    out = {}
    for raw in validate_param_defs(defs):
        name = raw["name"]
        if name in values and values[name] not in (None, ""):
            out[name] = _coerce_value(raw, values[name])
        elif raw.get("default") not in (None, ""):
            out[name] = _coerce_value(raw, raw["default"])
        elif raw["required"]:
            raise ParamError("missing required parameter: %s" % name, name)
        else:
            out[name] = None
    return out


def sample_values(defs):
    out = {}
    for p in validate_param_defs(defs):
        value = p.get("default")
        if value is None:
            value = p.get("example")
        if value is None:
            value = {"string": "sample", "number": 1,
                     "date": "1970-01-01", "bool": False}[p["type"]]
        out[p["name"]] = _coerce_value(p, value)
    return out
