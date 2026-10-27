"""Layanan autentikasi pemilik tunggal (Single-Owner Authentication) - Addendum v2.1."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.base import utcnow
from app.db.models import AuditLog, OwnerSession, OwnerUser

ITERATIONS = 600_000


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def hash_password(password: str) -> str:
    """Hash password menggunakan PBKDF2-HMAC-SHA256 dengan salt unik 16-byte."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    return f"pbkdf2_sha256${ITERATIONS}${salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifikasi password terhadap hash tersimpan dengan constant-time compare."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_key = parts[3]
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(key.hex(), expected_key)
    except (ValueError, TypeError):
        return False


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Jaga kompatibilitas antara PostgreSQL (aware) dan SQLite (naive saat read)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def get_owner(session: Session) -> OwnerUser | None:
    """Ambil akun pemilik tunggal dari database."""
    return session.scalar(select(OwnerUser).limit(1))


def is_initialized(session: Session) -> bool:
    """Periksa apakah sistem telah dibootstrap dengan akun pemilik."""
    return get_owner(session) is not None


def bootstrap_owner(
    session: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    full_name: str = "Roihan",
    bootstrap_token: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[OwnerUser, OwnerSession]:
    """Inisialisasi akun pemilik pertama dan satu-satunya."""
    if is_initialized(session):
        raise AuthError("already_initialized", "Sistem telah diinisialisasi; pendaftaran pemilik ditutup permanen", 403)

    norm_email = email.lower().strip()
    if settings.owner_email and norm_email != settings.owner_email.lower().strip():
        raise AuthError("email_disallowed", "Email tidak cocok dengan konfigurasi OWNER_EMAIL yang diizinkan", 403)

    if settings.bootstrap_token:
        if not bootstrap_token or not secrets.compare_digest(bootstrap_token.encode(), settings.bootstrap_token.encode()):
            raise AuthError("invalid_bootstrap_token", "Bootstrap token tidak valid atau tidak cocok", 403)

    if len(password) < 8:
        raise AuthError("weak_password", "Kata sandi minimal harus terdiri dari 8 karakter", 422)

    user = OwnerUser(
        email=norm_email,
        password_hash=hash_password(password),
        full_name=full_name.strip() or "Owner",
        is_active=True,
    )
    session.add(user)
    session.flush()

    sess = OwnerSession(
        user_id=user.id,
        session_token=generate_session_token(),
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None,
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
        last_activity_at=utcnow(),
        revoked=False,
    )
    session.add(sess)

    audit = AuditLog(
        actor="bootstrap",
        action="bootstrap_owner",
        entity_type="owner_user",
        entity_id=user.id,
        details={"email": norm_email, "ip": ip_address},
    )
    session.add(audit)
    session.commit()
    return user, sess


def login_owner(
    session: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[OwnerUser, OwnerSession]:
    """Login akun pemilik tunggal dengan rate limiting anti brute-force."""
    norm_email = email.lower().strip()
    user = session.scalar(select(OwnerUser).where(OwnerUser.email == norm_email))

    if user is None:
        audit = AuditLog(actor="unknown", action="login_failed", details={"email": norm_email, "reason": "user_not_found", "ip": ip_address})
        session.add(audit)
        session.commit()
        raise AuthError("invalid_credentials", "Email atau kata sandi tidak valid", 401)

    now = utcnow()
    locked = ensure_aware(user.locked_until)
    if locked and locked > now:
        remaining = int((locked - now).total_seconds())
        raise AuthError("account_locked", f"Akun terkunci sementara karena percobaan gagal berulang. Coba lagi dalam {remaining} detik", 429)

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
        audit = AuditLog(actor=user.email, action="login_failed", entity_type="owner_user", entity_id=user.id, details={"attempts": user.failed_login_attempts, "ip": ip_address})
        session.add(audit)
        session.commit()
        raise AuthError("invalid_credentials", "Email atau kata sandi tidak valid", 401)

    # Login sukses
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    sess = OwnerSession(
        user_id=user.id,
        session_token=generate_session_token(),
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None,
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_activity_at=now,
        revoked=False,
    )
    session.add(sess)

    audit = AuditLog(actor=user.email, action="login_success", entity_type="owner_user", entity_id=user.id, details={"ip": ip_address})
    session.add(audit)
    session.commit()
    return user, sess


def logout_session(session: Session, token: str) -> bool:
    """Cabut sesi aktif pemilik."""
    sess = session.scalar(select(OwnerSession).where(OwnerSession.session_token == token))
    if sess:
        sess.revoked = True
        session.commit()
        return True
    return False


def verify_active_session(session: Session, token: str) -> OwnerUser | None:
    """Verifikasi token sesi aktif."""
    if not token or len(token) < 16:
        return None
    now = utcnow()
    sess = session.scalar(
        select(OwnerSession).where(
            OwnerSession.session_token == token,
            OwnerSession.revoked.is_(False),
            OwnerSession.expires_at > now,
        )
    )
    if not sess:
        return None
    # Refresh activity timestamp
    sess.last_activity_at = now
    session.commit()
    return session.get(OwnerUser, sess.user_id)
