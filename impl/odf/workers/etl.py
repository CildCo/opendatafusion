import logging
from datetime import datetime, timezone

from odf.connectors.factory import sink_for, source_for
from odf.models import Datasource, Flow, FlowRun, FlowVersion
from odf.services.scheduler import release_run

log = logging.getLogger(__name__)


def build_select(table: str, cursor_col: str | None,
                 cursor_value: str | None, limit: int):
    where = ""
    params = {"limit": limit}
    if cursor_col and cursor_value:
        where = " where %s > :cursor" % cursor_col
        params["cursor"] = cursor_value
    return ("select * from %s%s order by %s limit :limit"
            % (table, where, cursor_col or "1")), params


def run_flow(session, flow_id: int, actor: str = "system") -> FlowRun:
    flow = session.get(Flow, flow_id)
    version = (session.query(FlowVersion)
               .filter_by(flow_id=flow_id, version=flow.current_version).one())
    dag = version.dag_json
    src = session.get(Datasource, dag["source_ds_id"])
    dst = session.get(Datasource, dag["sink_ds_id"])
    last = (session.query(FlowRun)
            .filter_by(flow_id=flow_id, status=2)
            .order_by(FlowRun.id.desc()).first())
    cursor_value = last.cursor_value if last else None

    run = FlowRun(flow_id=flow_id, status=1,
                  started_at=datetime.now(timezone.utc))
    session.add(run)
    session.commit()
    session.refresh(run)

    in_num = out_num = err_num = 0
    status = 3
    try:
        source = source_for(src, dag)
        sink = sink_for(dst, dag)
        rows, new_cursor = source.read(cursor_value,
                                       int(dag.get("batch", 1000)))
        in_num = len(rows)
        out_num = sink.write(rows)
        cursor_value = new_cursor
        status = 2
    except Exception:
        log.exception("flow %s failed", flow_id)
        err_num = 1
    finally:
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.in_num, run.out_num, run.err_num = in_num, out_num, err_num
        run.cursor_value = cursor_value
        session.commit()
        release_run(session, flow_id)
    return run
