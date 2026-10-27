"""Router autentikasi pemilik tunggal (Single-Owner Authentication API) - Addendum v2.1."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.service import (
    AuthError,
    bootstrap_owner,
    get_owner,
    hash_password,
    is_initialized,
    login_owner,
    logout_session,
    verify_active_session,
    verify_password,
)
from app.db.base import utcnow
from app.db.models import AuditLog
from app.security import COOKIE_NAME, extract_token, require_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


class BootstrapBody(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8)
    full_name: str = "Roihan"
    bootstrap_token: str | None = None


class LoginBody(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: str
    last_login_at: str | None


@router.get("/status")
def auth_status(request: Request, session: SessionDep):
    """Status inisialisasi single-owner dan status sesi saat ini."""
    init = is_initialized(session)
    token = extract_token(request)
    user = verify_active_session(session, token) if token else None

    # Jika menggunakan APP_LOCAL_TOKEN (mis. local development / test proxy)
    if not user and token:
        local_tok = getattr(request.app.state.settings, "app_local_token", "")
        if local_tok and token == local_tok:
            user = get_owner(session)

    return {
        "initialized": init,
        "authenticated": user is not None,
        "owner_email_configured": bool(request.app.state.settings.owner_email),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        } if user else None,
    }


def _set_auth_cookie(response: Response, request: Request, token: str):
    settings = request.app.state.settings
    max_age = settings.session_ttl_days * 86400
    is_https = request.url.scheme == "https" or settings.cookie_secure
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=max_age,
        path="/",
        secure=is_https,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post("/bootstrap")
def bootstrap(body: BootstrapBody, request: Request, response: Response, session: SessionDep):
    """Inisialisasi akun pemilik pertama dan satu-satunya. DITUTUP permanen setelah dibuat."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        user, sess = bootstrap_owner(
            session,
            request.app.state.settings,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            bootstrap_token=body.bootstrap_token,
            ip_address=ip,
            user_agent=ua,
        )
    except AuthError as e:
        raise HTTPException(e.status_code, e.message)

    _set_auth_cookie(response, request, sess.session_token)
    return {
        "status": "success",
        "message": "Akun pemilik tunggal berhasil dibootstrap",
        "token": sess.session_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
    }


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, session: SessionDep):
    """Login akun pemilik tunggal dengan proteksi rate limit anti brute-force."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        user, sess = login_owner(
            session,
            request.app.state.settings,
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
    except AuthError as e:
        raise HTTPException(e.status_code, e.message)

    _set_auth_cookie(response, request, sess.session_token)
    return {
        "status": "success",
        "token": sess.session_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
    }


@router.post("/logout")
def logout(request: Request, response: Response, session: SessionDep):
    """Cabut sesi login aktif dan bersihkan cookie."""
    token = extract_token(request)
    if token:
        logout_session(session, token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success", "message": "Sesi telah berakhir"}


@router.get("/me", dependencies=[Depends(require_token)])
def get_me(request: Request, session: SessionDep):
    """Profil pemilik yang sedang login."""
    token = extract_token(request)
    user = verify_active_session(session, token) if token else None
    if not user:
        user = get_owner(session)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pengguna pemilik tidak ditemukan")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.post("/change-password", dependencies=[Depends(require_token)])
def change_password(body: ChangePasswordBody, request: Request, session: SessionDep):
    """Ganti kata sandi pemilik dengan verifikasi kata sandi saat ini."""
    token = extract_token(request)
    user = verify_active_session(session, token) if token else None
    if not user:
        user = get_owner(session)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pengguna pemilik tidak ditemukan")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kata sandi lama tidak cocok")

    user.password_hash = hash_password(body.new_password)
    audit = AuditLog(actor=user.email, action="change_password", entity_type="owner_user", entity_id=user.id)
    session.add(audit)
    session.commit()
    return {"status": "success", "message": "Kata sandi berhasil diperbarui"}
