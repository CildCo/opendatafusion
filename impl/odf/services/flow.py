from odf.models import Flow, FlowVersion


def validate_dag(dag: dict) -> bool:
    required = ("source_ds_id", "sink_ds_id", "source_table", "sink_table")
    return all(dag.get(k) for k in required)


def create_flow(session, project_id, name, cron, dag):
    assert validate_dag(dag)
    f = Flow(project_id=project_id, name=name, cron=cron, status=0)
    session.add(f)
    session.flush()
    session.add(FlowVersion(flow_id=f.id, version=1, dag_json=dag,
                            created_by="system"))
    session.commit()
    session.refresh(f)
    return f


def update_flow(session, flow_id, dag, actor):
    assert validate_dag(dag)
    f = session.get(Flow, flow_id)
    f.current_version += 1
    session.add(FlowVersion(flow_id=flow_id, version=f.current_version,
                            dag_json=dag, created_by=actor))
    session.commit()
    return f
