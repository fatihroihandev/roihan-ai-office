"""Keamanan dan verifikasi akses API (Addendum v2.1 Single-Owner & Token Guard)."""
import secrets

from fastapi import HTTPException, Request, status

from app.auth.service import verify_active_session

COOKIE_NAME = "roihan_session"


def extract_token(request: Request) -> str | None:
    """Ekstrak token dari header Authorization Bearer atau Cookie sesi roihan_session."""
    header = request.headers.get("authorization", "")
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    return None


def require_token(request: Request) -> None:
    """Dependensi untuk seluruh endpoint yang dilindungi:
    Menerima token lokal backend (APP_LOCAL_TOKEN) atau sesi login pemilik sah (roihan_session).
    """
    token = extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token atau sesi autentikasi tidak ditemukan")

    # 1. Cek token lokal backend (untuk worker, CLI, dan automated test suite)
    expected_local = getattr(request.app.state.settings, "app_local_token", "")
    if expected_local and len(token) == len(expected_local):
        if secrets.compare_digest(token.encode("utf-8"), expected_local.encode("utf-8")):
            return

    # 2. Cek sesi pemilik tunggal aktif di database (Addendum v2.1)
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is not None:
        with session_factory() as s:
            user = verify_active_session(s, token)
            if user and user.is_active:
                request.state.owner = user
                return

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesi kedaluwarsa atau token tidak valid")
