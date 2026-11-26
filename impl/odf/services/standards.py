from odf.models import (Column, Dataset, Datasource, Standard,
                        StandardMapping)


def create_standard(session, project_id: int, code: str, name: str,
                    description: str = "") -> Standard:
    s = Standard(project_id=project_id, code=code, name=name,
                 description=description)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def list_standards(session, project_id: int):
    return (session.query(Standard).filter_by(project_id=project_id)
            .order_by(Standard.id).all())


def update_standard(session, project_id, standard_id, code, name,
                    description=""):
    row = session.get(Standard, standard_id)
    if not row or row.project_id != project_id:
        raise ValueError("standard not found")
    code = (code or "").strip()
    name = (name or "").strip()
    if not code or not name:
        raise ValueError("standard code and name are required")
    row.code = code[:64]
    row.name = name[:128]
    row.description = (description or "")[:4000]
    session.commit()
    session.refresh(row)
    return row


def delete_standard(session, project_id, standard_id):
    row = session.get(Standard, standard_id)
    if not row or row.project_id != project_id:
        raise ValueError("standard not found")
    session.query(StandardMapping).filter_by(standard_id=standard_id).delete(
        synchronize_session=False)
    session.delete(row)
    session.commit()
    return {"deleted": True}


def map_standard(session, project_id, standard_id, dataset_id,
                 column_name):
    standard = session.get(Standard, standard_id)
    if not standard or standard.project_id != project_id:
        raise ValueError("standard not found")
    dataset = session.get(Dataset, dataset_id)
    datasource = session.get(Datasource, dataset.datasource_id) \
        if dataset else None
    if not datasource or datasource.project_id != project_id:
        raise ValueError("dataset not found")
    column = (session.query(Column)
              .filter_by(dataset_id=dataset_id, name=column_name).first())
    if not column:
        raise ValueError("column not found")
    existing = (session.query(StandardMapping)
                .filter_by(dataset_id=dataset_id,
                           column_name=column_name).first())
    if existing:
        existing.standard_id = standard_id
    else:
        existing = StandardMapping(standard_id=standard_id,
                                   dataset_id=dataset_id,
                                   column_name=column_name)
        session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def unmap_standard(session, project_id, mapping_id):
    row = session.get(StandardMapping, mapping_id)
    dataset = session.get(Dataset, row.dataset_id) if row else None
    datasource = session.get(Datasource, dataset.datasource_id) \
        if dataset else None
    if not row or not datasource or datasource.project_id != project_id:
        raise ValueError("mapping not found")
    session.delete(row)
    session.commit()
    return {"deleted": True}


def list_mappings(session, dataset_id: int):
    return (session.query(StandardMapping).filter_by(dataset_id=dataset_id)
            .order_by(StandardMapping.id).all())


def compliance(session, dataset_id: int):
    cols = (session.query(Column).filter_by(dataset_id=dataset_id)
            .order_by(Column.id).all())
    mappings = {m.column_name: m for m in list_mappings(session, dataset_id)}
    return [{"column": c.name, "mapped": c.name in mappings,
             "standard_id": mappings[c.name].standard_id
             if c.name in mappings else None} for c in cols]
