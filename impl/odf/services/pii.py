import re

from odf.models import Column, ColumnPolicy, Dataset, Datasource

NAME_RULES = [
    ("pii", "email", re.compile(r"e[-_]?mail", re.I)),
    ("pii", "phone", re.compile(r"phone|mobile|tel", re.I)),
    ("pii", "id_card", re.compile(r"id[-_]?card|identity|passport", re.I)),
    ("pii", "name", re.compile(r"(^|_)(first|last|full|user|customer|real)[-_]?name", re.I)),
    ("pii", "address", re.compile(r"address|street|city|zip", re.I)),
    ("confidential", "bank", re.compile(r"bank|iban|account[-_]?no", re.I)),
    ("confidential", "salary", re.compile(r"salary|income|wage", re.I)),
    ("sensitive", "secret", re.compile(r"password|passwd|token|secret|api[-_]?key", re.I)),
]

VALUE_RULES = [
    ("pii", "email", re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")),
    ("pii", "phone", re.compile(r"^1[3-9]\d{9}$")),
    ("pii", "id_card", re.compile(r"^\d{17}[\dXx]$")),
    ("pii", "bank", re.compile(r"^\d{12,19}$")),
]


def _dataset(session, project_id, dataset_id):
    ds = session.get(Dataset, dataset_id)
    if not ds:
        raise ValueError("dataset not found")
    datasource = session.get(Datasource, ds.datasource_id)
    if not datasource or datasource.project_id != project_id:
        raise ValueError("dataset not found")
    return ds, datasource


def scan(session, project_id, dataset_id, sample_limit=20):
    ds, datasource = _dataset(session, project_id, dataset_id)
    columns = (session.query(Column).filter_by(dataset_id=ds.id)
               .order_by(Column.id).all())
    samples = []
    try:
        from odf.services.catalog import dataset_sample
        sampled = dataset_sample(session, project_id, dataset_id,
                                 sample_limit)
        samples = sampled.get("rows") or []
    except Exception:
        samples = []
    existing = {(p.column_name): p for p in
                session.query(ColumnPolicy).filter_by(
                    datasource_id=datasource.id,
                    schema_name=ds.schema_name or "",
                    table_name=ds.table_name).all()}
    findings = []
    for column in columns:
        hit = None
        for classification, kind, pattern in NAME_RULES:
            if pattern.search(column.name):
                hit = (classification, kind, "column name")
                break
        if hit is None:
            values = [str(row.get(column.name)) for row in samples
                      if row.get(column.name) is not None]
            for classification, kind, pattern in VALUE_RULES:
                matched = sum(1 for value in values[:20]
                              if pattern.match(value.strip()))
                if matched >= max(1, len(values[:20]) // 2):
                    hit = (classification, kind, "sample values")
                    break
        if not hit:
            continue
        policy = existing.get(column.name)
        findings.append({
            "column": column.name, "type": column.data_type,
            "classification": hit[0], "detected_as": hit[1],
            "evidence": hit[2],
            "masked": bool(policy), "mask_type": policy.mask_type
            if policy else None})
    return {"dataset_id": dataset_id, "datasource_id": datasource.id,
            "schema": ds.schema_name, "table": ds.table_name,
            "sampled_rows": len(samples), "findings": findings}


def apply(session, project_id, dataset_id, actor):
    result = scan(session, project_id, dataset_id)
    ds, datasource = _dataset(session, project_id, dataset_id)
    changed = 0
    for finding in result["findings"]:
        if finding["masked"]:
            continue
        session.add(ColumnPolicy(
            project_id=project_id, datasource_id=datasource.id,
            schema_name=ds.schema_name or "", table_name=ds.table_name,
            column_name=finding["column"],
            classification=finding["classification"], mask_type="redact",
            exempt_roles_json=[], source="scan", created_by=actor))
        changed += 1
    session.commit()
    result["applied"] = changed
    return result
