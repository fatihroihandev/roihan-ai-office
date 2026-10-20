import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import AuditLog, Project, ProjectFile
from app.projects.storage import ProjectStorage, StorageError
from app.projects.uploads import FileKind, UploadError, validate_upload
from app.schemas.projects import FileOut, ProjectCreate, ProjectOut, ProjectUpdate
from app.security import require_token

logger = logging.getLogger("roihan.projects")
ACTOR = "ceo"  # single-user lokal; identitas aktor akan mengikuti autentikasi jika multi-user ditambahkan

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_token)])


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def get_storage(request: Request) -> ProjectStorage:
    return ProjectStorage(request.app.state.settings.projects_dir)


SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[ProjectStorage, Depends(get_storage)]


def _audit(session: Session, action: str, entity_type: str, entity_id: str, details: dict | None = None) -> None:
    session.add(AuditLog(actor=ACTOR, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def _project_or_404(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan")
    return project


def _file_or_404(session: Session, project_id: str, file_id: str) -> ProjectFile:
    f = session.get(ProjectFile, file_id)
    if f is None or f.project_id != project_id or f.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File tidak ditemukan")
    return f


def _metadata(project: Project) -> dict:
    return {"id": project.id, "name": project.name, "description": project.description,
            "status": project.status, "created_at": project.created_at, "updated_at": project.updated_at}


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, session: SessionDep, storage: StorageDep):
    project = Project(name=body.name, description=body.description)
    session.add(project)
    session.flush()
    storage.create_layout(project.id)
    storage.write_metadata(project.id, _metadata(project))
    _audit(session, "project.create", "project", project.id, {"name": project.name})
    session.commit()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(active|archived)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    q = select(Project).where(Project.deleted_at.is_(None))
    if status_filter:
        q = q.where(Project.status == status_filter)
    return session.scalars(q.order_by(Project.created_at.desc()).limit(limit).offset(offset)).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, session: SessionDep):
    return _project_or_404(session, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, session: SessionDep, storage: StorageDep):
    project = _project_or_404(session, project_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nama proyek tidak boleh kosong")
    for field, value in changes.items():
        setattr(project, field, value)
    session.flush()
    storage.write_metadata(project.id, _metadata(project))
    _audit(session, "project.update", "project", project.id, {"fields": sorted(changes)})
    session.commit()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, session: SessionDep):
    """Soft delete: data dan file asli dipertahankan sesuai kebijakan retensi (Bagian 13.3)."""
    project = _project_or_404(session, project_id)
    project.deleted_at = utcnow()
    _audit(session, "project.delete", "project", project.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: str,
    request: Request,
    session: SessionDep,
    storage: StorageDep,
    kind: Annotated[FileKind, Form()],
    file: Annotated[UploadFile, File()],
):
    project = _project_or_404(session, project_id)
    max_bytes = request.app.state.settings.max_upload_bytes

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes + 1024 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Ukuran unggahan melebihi batas")

    chunks, total = [], 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                f"Ukuran file melebihi batas {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    data = b"".join(chunks)

    try:
        safe_name, content_type = validate_upload(kind, file.filename, data, max_bytes)
        stored_name, rel_path, digest = storage.save_file(project.id, kind, safe_name, data)
    except UploadError as e:
        raise HTTPException(e.status, str(e))
    except StorageError as e:
        logger.error("storage error", extra={"error": str(e)})
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Gagal menyimpan file")

    record = ProjectFile(
        project_id=project.id, kind=kind.value, original_name=(file.filename or "")[:255], stored_name=stored_name,
        relative_path=rel_path, content_type=content_type, size_bytes=len(data), sha256=digest,
    )
    session.add(record)
    session.flush()
    _audit(session, "file.upload", "project_file", record.id,
           {"project_id": project.id, "kind": kind.value, "name": stored_name, "size": len(data), "sha256": digest})
    session.commit()
    return record


@router.get("/{project_id}/files", response_model=list[FileOut])
def list_files(project_id: str, session: SessionDep, kind: FileKind | None = None):
    _project_or_404(session, project_id)
    q = select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.deleted_at.is_(None))
    if kind:
        q = q.where(ProjectFile.kind == kind.value)
    return session.scalars(q.order_by(ProjectFile.created_at.desc())).all()


@router.get("/{project_id}/files/{file_id}/download")
def download_file(project_id: str, file_id: str, session: SessionDep, storage: StorageDep):
    _project_or_404(session, project_id)
    record = _file_or_404(session, project_id, file_id)
    try:
        path = storage.resolve_file(project_id, record.relative_path)
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File tidak ditemukan")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File tidak ditemukan di penyimpanan")
    return FileResponse(
        path, media_type="application/octet-stream", filename=record.stored_name,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(project_id: str, file_id: str, session: SessionDep):
    """Soft delete: file asli tetap ada di disk (Bagian 13.3)."""
    _project_or_404(session, project_id)
    record = _file_or_404(session, project_id, file_id)
    record.deleted_at = utcnow()
    _audit(session, "file.delete", "project_file", record.id, {"project_id": project_id})
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
