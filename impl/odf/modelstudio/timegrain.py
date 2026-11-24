import calendar
import re
from datetime import date, datetime, timedelta

GRAINS = ("day", "week", "month", "quarter", "year")
COMPARE_MODES = ("none", "previous", "year")

_PG = {"postgres", "postgresql", "opengauss", "gaussdb", "kingbase",
       "redshift"}
_TRINO = {"trino", "duckdb"}
_MYSQL = {"mysql", "mariadb", "tidb", "oceanbase", "doris", "starrocks"}
_ORACLE = {"oracle", "dm"}
_HIVE = {"hive"}


class TimeGrainError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = str(detail or "")[:64]
        super().__init__(code)


_MESSAGES = {
    "grain": "time grain must be day, week, month, quarter or year",
    "dialect": "time grains are not supported for this datasource",
    "column": "time column is not in the dataset output",
    "dimension": "time column must not also be listed as a dimension",
    "compare": "compare must be none, previous or year",
    "requires_time": "comparison requires a time grain",
}


def timegrain_message(error):
    return _MESSAGES.get(error.code, "invalid time definition")


def supports_time_grain(kind):
    try:
        bucket_sql(kind, "col", "month")
    except TimeGrainError:
        return False
    return True


def bucket_sql(kind, column, grain):
    if grain not in GRAINS:
        raise TimeGrainError("grain")
    dialect = (kind or "").lower()
    sql = "CAST(%s AS DATE)" % column
    if dialect in _PG or dialect in _TRINO:
        return "date_trunc('%s', %s)" % (grain, column)
    if dialect in _MYSQL:
        return {
            "day": "DATE(%s)" % column,
            "week": "DATE_SUB(DATE(%s), INTERVAL WEEKDAY(%s) DAY)"
                    % (column, column),
            "month": "DATE_FORMAT(%s, '%%Y-%%m-01')" % column,
            "quarter": "MAKEDATE(YEAR(%s), 1) + INTERVAL "
                       "(QUARTER(%s) - 1) QUARTER" % (column, column),
            "year": "DATE_FORMAT(%s, '%%Y-01-01')" % column,
        }[grain]
    if dialect == "sqlite":
        return {
            "day": "date(%s)" % column,
            "week": "date(%s, '-' || ((strftime('%%w', %s) + 6) %% 7) "
                    "|| ' days')" % (column, column),
            "month": "date(%s, 'start of month')" % column,
            "quarter": "date(%s, '-' || ((cast(strftime('%%m', %s) AS "
                       "INTEGER) - 1) %% 3) || ' months', "
                       "'start of month')" % (column, column),
            "year": "date(%s, 'start of year')" % column,
        }[grain]
    if dialect in _ORACLE:
        fmt = {"day": None, "week": "'IW'", "month": "'MM'",
               "quarter": "'Q'", "year": "'YYYY'"}[grain]
        return "TRUNC(%s)" % column if fmt is None else \
            "TRUNC(%s, %s)" % (column, fmt)
    if dialect in ("mssql", "sqlserver"):
        return {
            "day": "CAST(%s AS DATE)" % column,
            "week": "DATEADD(day, -(DATEDIFF(day, 0, %s) %% 7), "
                    "CAST(%s AS DATE))" % (column, column),
            "month": "DATEFROMPARTS(YEAR(%s), MONTH(%s), 1)"
                     % (column, column),
            "quarter": "DATEFROMPARTS(YEAR(%s), ((MONTH(%s) - 1) / 3) "
                       "* 3 + 1, 1)" % (column, column),
            "year": "DATEFROMPARTS(YEAR(%s), 1, 1)" % (column, column),
        }[grain]
    if dialect == "clickhouse":
        return {
            "day": "toDate(%s)" % column,
            "week": "toMonday(%s)" % column,
            "month": "toStartOfMonth(%s)" % column,
            "quarter": "toStartOfQuarter(%s)" % column,
            "year": "toStartOfYear(%s)" % column,
        }[grain]
    if dialect in _HIVE:
        return {
            "day": sql,
            "week": "DATE_SUB(NEXT_DAY(%s, 'MON'), 7)" % column,
            "month": "TRUNC(%s, 'MM')" % column,
            "quarter": "TRUNC(%s, 'Q')" % column,
            "year": "TRUNC(%s, 'YYYY')" % column,
        }[grain]
    raise TimeGrainError("dialect")


def parse_time(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _add_months(value, months):
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _shift_datetime(value, unit, step):
    if unit == "day":
        return value + timedelta(days=step)
    if unit == "week":
        return value + timedelta(weeks=step)
    if unit == "month":
        return _add_months(value, step)
    if unit == "quarter":
        return _add_months(value, 3 * step)
    if unit == "year":
        return _add_months(value, 12 * step)
    raise TimeGrainError("grain", unit)


def shift_time(value, unit, step):
    parsed = parse_time(value)
    if parsed is None:
        return value
    shifted = _shift_datetime(parsed, unit, step)
    if isinstance(value, datetime):
        return shifted
    if isinstance(value, date):
        return shifted.date()
    text = value.strip()
    if "T" in text or " " in text:
        return shifted.isoformat()
    return shifted.date().isoformat()


def next_bucket(value, grain):
    return shift_time(value, grain, 1)
