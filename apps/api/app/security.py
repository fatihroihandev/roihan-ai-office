import secrets

from fastapi import HTTPException, Request, status


def require_token(request: Request) -> None:
    """Dependensi untuk endpoint non-publik: Authorization: Bearer <APP_LOCAL_TOKEN>."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    expected = request.app.state.settings.app_local_token
    if scheme.lower() != "bearer" or not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak valid")
