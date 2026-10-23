from odf.models import Project, ProjectMember


def create_project(session, code: str, name: str) -> Project:
    p = Project(code=code, name=name, status=1)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def list_projects(session):
    return session.query(Project).order_by(Project.id).all()


def list_projects_for_user(session, user):
    if user.role == "admin":
        return list_projects(session)
    ids = [m.project_id for m in
           session.query(ProjectMember).filter_by(user_id=user.id).all()]
    if not ids:
        return []
    return (session.query(Project)
            .filter(Project.id.in_(ids)).order_by(Project.id).all())


def add_member(session, project_id: int, user_id: int,
               role: str = "viewer") -> ProjectMember:
    m = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def list_members(session, project_id: int):
    return (session.query(ProjectMember)
            .filter_by(project_id=project_id).order_by(ProjectMember.id).all())
