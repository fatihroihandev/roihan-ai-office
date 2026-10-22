"""Event real-time (Bagian 16.2). Database adalah sumber kebenaran; WebSocket hanya mendistribusikan.

Browser tidak dapat mengirim header Authorization pada WebSocket, dan token lokal tidak boleh masuk ke browser.
Karena itu klien meminta tiket sekali-pakai lewat proxy server (yang menambahkan token), lalu memakainya di sini.
"""
import asyncio
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.db.models import TaskEvent
from app.schemas.tasks import EventOut
from app.security import require_token

TICKET_TTL_S = 30
POLL_INTERVAL_S = 0.5
BATCH = 200

router = APIRouter(prefix="/api", tags=["events"])


def _serialize(e: TaskEvent) -> dict:
    return {
        "seq": e.seq, "type": e.type, "entity_type": "power" if e.task_id == "power" else "task", "entity_id": e.task_id, "project_id": e.project_id,
        "occurred_at": e.created_at.isoformat(), "payload": {"from": e.from_status, "to": e.to_status,
                                                              "reason": e.reason, **(e.payload or {})},
    }


def _fetch(session_factory, since: int, limit: int = BATCH) -> list[TaskEvent]:
    with session_factory() as s:
        return list(s.scalars(select(TaskEvent).where(TaskEvent.seq > since).order_by(TaskEvent.seq).limit(limit)))


def _max_seq(session_factory) -> int:
    with session_factory() as s:
        return s.scalar(select(func.coalesce(func.max(TaskEvent.seq), 0)))


@router.get("/events", response_model=list[EventOut], dependencies=[Depends(require_token)])
def list_events(request: Request, since: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    """Catch-up REST: ambil event setelah `since` (dipakai setelah reconnect)."""
    return _fetch(request.app.state.session_factory, since, limit)


@router.post("/events/ticket", dependencies=[Depends(require_token)])
def create_ticket(request: Request):
    tickets: dict[str, float] = request.app.state.ws_tickets
    now = time.monotonic()
    for k in [k for k, exp in tickets.items() if exp < now]:
        del tickets[k]
    ticket = secrets.token_urlsafe(24)
    tickets[ticket] = now + TICKET_TTL_S
    return {"ticket": ticket, "expires_in": TICKET_TTL_S}


@router.websocket("/ws")
async def ws_events(ws: WebSocket, ticket: str = "", since: int | None = None):
    app = ws.app
    origin = ws.headers.get("origin")
    if origin is not None and origin not in app.state.settings.cors_origins:
        await ws.close(code=1008)
        return
    expires = app.state.ws_tickets.pop(ticket, None)  # sekali pakai
    if expires is None or expires < time.monotonic():
        await ws.close(code=1008)
        return

    await ws.accept()
    sf = app.state.session_factory
    cursor = _max_seq(sf) if since is None else since
    await ws.send_json({"type": "hello", "last_seq": cursor})

    gone = asyncio.Event()

    async def drain():  # deteksi klien yang memutus koneksi
        try:
            while True:
                await ws.receive_text()
        except (WebSocketDisconnect, RuntimeError):
            gone.set()

    reader = asyncio.create_task(drain())
    try:
        while not gone.is_set():
            events = await asyncio.to_thread(_fetch, sf, cursor)
            for e in events:
                await ws.send_json(_serialize(e))
                cursor = e.seq
            if len(events) < BATCH:
                try:
                    await asyncio.wait_for(gone.wait(), timeout=POLL_INTERVAL_S)
                except asyncio.TimeoutError:
                    pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader.cancel()
