import csv
import io


def dashboard_csv(result):
    widgets = [(widget_id, data)
               for widget_id, data in (result.get("widgets") or {}).items()
               if data.get("rows")]
    if not widgets:
        raise ValueError("dashboard has no tabular data")
    multi = len(widgets) > 1
    columns = []
    for _, data in widgets:
        for name in data.get("columns") or []:
            if name not in columns:
                columns.append(name)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow((["widget"] if multi else []) + columns)
    for widget_id, data in widgets:
        for row in data.get("rows") or []:
            writer.writerow(
                ([widget_id] if multi else [])
                + [row.get(name, "") for name in columns])
    return buf.getvalue(), len(widgets)
