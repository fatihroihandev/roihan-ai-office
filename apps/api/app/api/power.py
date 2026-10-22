"""Office Power Control (Addendum v2.3, Bagian 29.A.12): OFF/ON, status global, checkpoint, dan item pemulihan.

Semua rute memerlukan token. UI tidak boleh menganggap permintaan berhasil sebelum respons backend mengonfirmasi; status akhir dibaca
dari `GET /api/power` (potret konsisten dari database).
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PowerCommand, RecoveryItem, RecoveryLog, TaskCheckpoint
from app.power import service as power
from app.power.checkpoints import CheckpointManager
from app.security import require_token

router = APIRouter(prefix="/api/power", tags=["power"], dependencies=[Depends(require_token)])

_CODES = {"conflict": 409, "not_found": 404, "invalid": 422}


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _controller(request: Request) -> power.PowerController:
    return request.app.state.power


def _http(e: power.PowerError) -> HTTPException:
    return HTTPException(_CODES.get(e.code, 409), str(e))


@router.get("")
def status(session: SessionDep):
    return power.snapshot(session)


@router.post("/off")
async def off(request: Request, response: Response):
    try:
        out = await _controller(request).request_off()
    except power.PowerError as e:
        raise _http(e) from e
    response.status_code = 202 if out["accepted"] else 200
    return out


@router.post("/on")
async def on(request: Request, response: Response):
    try:
        out = await _controller(request).request_on()
    except power.PowerError as e:
        raise _http(e) from e
    response.status_code = 202 if out["accepted"] else 200
    return out


@router.get("/commands")
def commands(session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    rows = session.scalars(select(PowerCommand).order_by(PowerCommand.created_at.desc()).limit(limit))
    return [power._command_view(c) for c in rows]


@router.get("/commands/{command_id}")
def command(command_id: str, session: SessionDep):
    c = session.get(PowerCommand, command_id)
    if c is None:
        raise HTTPException(404, "Perintah tidak ditemukan")
    return power._command_view(c)


@router.get("/checkpoints")
def checkpoints(session: SessionDep, task_id: str | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    q = select(TaskCheckpoint).order_by(TaskCheckpoint.created_at.desc()).limit(limit)
    if task_id:
        q = q.where(TaskCheckpoint.task_id == task_id)
    return [CheckpointManager.brief(c) for c in session.scalars(q)]


@router.get("/tasks/{task_id}/checkpoints")
def task_checkpoints(task_id: str, session: SessionDep):
    rows = session.scalars(select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id).order_by(TaskCheckpoint.created_at.desc()))
    return [CheckpointManager.brief(c) for c in rows]


@router.get("/recovery")
def recovery(session: SessionDep, scope: Literal["open", "all"] = "open"):
    q = select(RecoveryItem).order_by(RecoveryItem.created_at.desc()).limit(100)
    if scope == "open":
        q = q.where(RecoveryItem.status == "open")
    return [power.item_view(i) for i in session.scalars(q)]


@router.get("/recovery/log")
def recovery_log(session: SessionDep, command_id: str | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    q = select(RecoveryLog).order_by(RecoveryLog.created_at.desc()).limit(limit)
    if command_id:
        q = q.where(RecoveryLog.command_id == command_id)
    return [{"id": r.id, "command_id": r.command_id, "source": r.source, "task_id": r.task_id, "project_id": r.project_id, "action": r.action,
             "checkpoint_id": r.checkpoint_id, "detail": r.detail, "created_at": r.created_at.isoformat()} for r in session.scalars(q)]


class ResolveIn(BaseModel):
    resolution: Literal["requeue", "cancel", "confirmed_done", "confirmed_not_done", "acknowledged"]


@router.post("/recovery/{item_id}/resolve")
def resolve(item_id: str, body: ResolveIn, request: Request, session: SessionDep):
    try:
        item = _controller(request).recovery.resolve_item(session, item_id, body.resolution)
        session.commit()
    except power.PowerError as e:
        session.rollback()
        raise _http(e) from e
    return power.item_view(item)
