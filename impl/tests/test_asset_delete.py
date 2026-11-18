from odf.db import SessionLocal
from odf.models import (ApiCallStat, Asset, AssetVersion, InterfaceGrant,
                        InterfaceRequest, Job, LineageEdge, PipelineNodeRun,
                        Project, ShareLink)
from odf.assets.service import create_asset, delete_asset


def _project(pid):
    with SessionLocal() as s:
        if not s.get(Project, pid):
            s.add(Project(id=pid, code="del%d" % pid, name="del"))
            s.commit()


def test_delete_asset_removes_versions_jobs_and_links():
    _project(921)
    with SessionLocal() as s:
        a = create_asset(s, 921, "pipeline", "cleanup", {"nodes": [],
                                                        "edges": []}, "1")
        aid = a.id
        v = s.get(AssetVersion, a.draft_version_id)
        job = Job(asset_id=aid, asset_type="pipeline", status="success")
        s.add(job)
        s.flush()
        s.add(PipelineNodeRun(job_id=job.id, asset_id=aid, node_id="n",
                              status="success"))
        s.add(ShareLink(project_id=921, asset_id=aid,
                        asset_type="pipeline", token_hash="h-%d" % aid,
                        created_by="1",
                        expires_at=v.created_at))
        s.add(InterfaceGrant(interface_asset_id=aid, owner_project_id=921,
                             grantee_project_id=921, granted_by="1"))
        s.add(InterfaceRequest(interface_asset_id=aid,
                               owner_project_id=921,
                               grantee_project_id=921, requested_by="1",
                               note="", status="pending"))
        s.add(ApiCallStat(day=v.created_at.date(), api_id=aid, ak="k"))
        s.add(LineageEdge(project_id=921, asset_id=aid, from_type="pipeline",
                          from_id=str(aid), from_ref="x", to_type="dataset",
                          to_id=str(aid), to_ref="y"))
        s.commit()
    delete_asset(s, aid, 921)
    with SessionLocal() as s:
        assert s.get(Asset, aid) is None
        assert not s.query(AssetVersion).filter_by(asset_id=aid).count()
        assert not s.query(Job).filter_by(asset_id=aid).count()
        assert not s.query(PipelineNodeRun).filter_by(asset_id=aid).count()
        assert not s.query(ShareLink).filter_by(asset_id=aid).count()
        assert not s.query(InterfaceGrant).filter_by(
            interface_asset_id=aid).count()
        assert not s.query(ApiCallStat).filter_by(api_id=aid).count()
        assert not s.query(LineageEdge).filter_by(asset_id=aid).count()
        assert not s.query(LineageEdge).filter_by(to_id=str(aid)).count()


def test_delete_asset_is_project_scoped():
    _project(922)
    with SessionLocal() as s:
        a = create_asset(s, 922, "dataset", "keep", {"columns": []}, "1")
        aid = a.id
    try:
        delete_asset(s, aid, 999)
    except ValueError as error:
        assert "not found" in str(error)
    else:
        raise AssertionError("expected the wrong project to be rejected")
    with SessionLocal() as s:
        assert s.get(Asset, aid) is not None
        delete_asset(s, aid, 922)
