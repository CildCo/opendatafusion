from odf.models import Column, Dataset, Standard, StandardMapping


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


def map_standard(session, standard_id: int, dataset_id: int,
                 column_name: str) -> StandardMapping:
    m = StandardMapping(standard_id=standard_id, dataset_id=dataset_id,
                        column_name=column_name)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


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
