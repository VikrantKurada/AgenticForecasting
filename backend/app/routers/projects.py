from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_

from app import models, schemas
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_or_404(db, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", status_code=201, response_model=schemas.ProjectOut)
def create_project(body: schemas.ProjectCreate, db=Depends(get_db)):
    project = models.Project(name=body.name, description=body.description)
    db.add(project)
    db.flush()
    record_event(
        db, actor="user", event_type="project_created",
        project_id=project.id, payload={"name": project.name},
    )
    db.commit()
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(q: str = "", db=Depends(get_db)):
    query = db.query(models.Project)
    if q:
        needle = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Project.name).like(needle),
                func.lower(models.Project.description).like(needle),
            )
        )
    return query.order_by(models.Project.updated_at.desc()).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db=Depends(get_db)):
    return _get_or_404(db, project_id)


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: str, body: schemas.ProjectUpdate, db=Depends(get_db)):
    project = _get_or_404(db, project_id)
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    record_event(
        db, actor="user", event_type="project_updated",
        project_id=project.id, payload=body.model_dump(exclude_none=True),
    )
    db.commit()
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db=Depends(get_db)):
    project = _get_or_404(db, project_id)
    record_event(
        db, actor="user", event_type="project_deleted",
        project_id=project.id, payload={"name": project.name},
    )
    db.delete(project)
    db.commit()
