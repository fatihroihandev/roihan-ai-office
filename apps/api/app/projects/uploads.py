"""Validasi unggahan. File hanya disimpan, tidak pernah dieksekusi atau diekstrak."""
import re
import unicodedata
from enum import Enum


class FileKind(str, Enum):
    master = "master"
    requirement = "requirement"
    reference = "reference"
    asset = "asset"


KIND_DIRS = {
    FileKind.master: "input",
    FileKind.requirement: "input/requirements",
    FileKind.reference: "input/references",
    FileKind.asset: "input/assets",
}

TEXT_EXTS = {"md", "txt", "json", "yaml", "yml", "csv"}
DOC_EXTS = {"pdf", "docx"}
IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}  # SVG sengaja ditolak (dapat memuat script)

ALLOWED_EXTS = {
    FileKind.master: {"md"},
    FileKind.requirement: TEXT_EXTS | DOC_EXTS,
    FileKind.reference: TEXT_EXTS | DOC_EXTS | IMAGE_EXTS,
    FileKind.asset: IMAGE_EXTS | DOC_EXTS | {"txt", "json", "csv"},
}

CONTENT_TYPES = {
    "md": "text/markdown", "txt": "text/plain", "json": "application/json", "yaml": "application/yaml",
    "yml": "application/yaml", "csv": "text/csv", "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
}

_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
MAX_NAME_LEN = 100


class UploadError(ValueError):
    """Unggahan ditolak. `status` dipakai sebagai kode HTTP."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def sanitize_filename(raw: str | None) -> str:
    """Ambil nama dasar yang aman; tolak jika tidak ada yang tersisa."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).lstrip(".")
    if len(name) > MAX_NAME_LEN:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: MAX_NAME_LEN - len(ext) - 1] + dot + ext) if dot else name[:MAX_NAME_LEN]
    stem = name.rsplit(".", 1)[0].lower()
    if not name or stem in _RESERVED:
        raise UploadError("Nama file tidak valid")
    return name


def extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _check_content(ext: str, data: bytes) -> None:
    ok = True
    if ext in TEXT_EXTS:
        ok = _is_text(data)
    elif ext == "pdf":
        ok = data.startswith(b"%PDF-")
    elif ext == "docx":
        ok = data.startswith(b"PK\x03\x04")
    elif ext == "png":
        ok = data.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in {"jpg", "jpeg"}:
        ok = data.startswith(b"\xff\xd8\xff")
    elif ext == "gif":
        ok = data[:6] in {b"GIF87a", b"GIF89a"}
    elif ext == "webp":
        ok = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if not ok:
        raise UploadError("Isi file tidak sesuai dengan ekstensinya")


def validate_upload(kind: FileKind, filename: str | None, data: bytes, max_bytes: int) -> tuple[str, str]:
    """Kembalikan (nama_aman, content_type) atau lempar UploadError."""
    name = sanitize_filename(filename)
    ext = extension(name)
    if ext not in ALLOWED_EXTS[kind]:
        allowed = ", ".join(sorted(ALLOWED_EXTS[kind]))
        raise UploadError(f"Ekstensi tidak diizinkan untuk kategori '{kind.value}'. Diizinkan: {allowed}")
    if len(data) == 0:
        raise UploadError("File kosong")
    if len(data) > max_bytes:
        raise UploadError(f"Ukuran file melebihi batas {max_bytes // (1024 * 1024)} MB", status=413)
    _check_content(ext, data)
    return name, CONTENT_TYPES[ext]
