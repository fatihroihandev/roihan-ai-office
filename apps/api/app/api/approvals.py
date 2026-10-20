from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import service
from app.approvals.service import ApprovalError
from app.db.models import Approval
from app.schemas.approvals import ApprovalOut, Decision
from app.security import require_token

router = APIRouter(prefix="/api", tags=["approvals"], dependencies=[Depends(require_token)])
ACTOR = "ceo"  # pemegang token lokal adalah CEO (single-user)


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _get(session: Session, approval_id: str) -> Approval:
    a = session.get(Approval, approval_id)
    if a is None:
        raise HTTPException(404, "Approval tidak ditemukan")
    return a


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(session: SessionDep, status_filter: Annotated[str | None, Query(alias="status", pattern="^(pending|approved|rejected|expired|cancelled)$")] = None,
                   project_id: str | None = None, task_id: str | None = None,
                   limit: Annotated[int, Query(ge=1, le=200)] = 100):
    q = select(Approval)
    if status_filter:
        q = q.where(Approval.status == status_filter)
    if project_id:
        q = q.where(Approval.project_id == project_id)
    if task_id:
        q = q.where(Approval.task_id == task_id)
    return list(session.scalars(q.order_by(Approval.created_at.desc()).limit(limit)))


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: str, session: SessionDep):
    return _get(session, approval_id)


def _decide(approval_id: str, decision: str, body: Decision, session: Session) -> Approval:
    approval = _get(session, approval_id)
    try:
        service.decide(session, approval, decision, ACTOR, body.reason)
    except ApprovalError as e:
        session.commit()  # kedaluwarsa/isi berubah mengubah status approval; simpan perubahan itu
        raise HTTPException(409, e.message)
    session.commit()
    return approval


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: str, session: SessionDep, body: Decision | None = None):
    return _decide(approval_id, "approved", body or Decision(), session)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
def reject(approval_id: str, session: SessionDep, body: Decision | None = None):
    return _decide(approval_id, "rejected", body or Decision(), session)
