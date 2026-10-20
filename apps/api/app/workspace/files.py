"""Akses file workspace yang dikurung. Agent hanya boleh menyentuh `workspace/source-code` proyeknya."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 100_000
MAX_FILES = 200
MAX_TOTAL_BYTES = 2_000_000
MAX_PATH_CHARS = 200

CODE_EXTS = {"py", "md", "txt", "json", "toml", "cfg", "ini", "yaml", "yml", "csv"}
DOC_EXTS = {"md", "txt"}

_PART = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")  # tanpa awalan titik: .git, .env, dan sejenisnya tertolak
_DRIVE = re.compile(r"^[A-Za-z]:")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_IGNORED_DIRS = {"__pycache__", "node_modules", "venv"}


class WorkspaceError(ValueError):
    pass


@dataclass
class FileInfo:
    path: str
    size: int


class WorkspaceFiles:
    def __init__(self, root: Path):
        self.root = root.resolve()

    # -- validasi path -----------------------------------------------------------

    def check_relative(self, rel: str) -> list[str]:
        """Validasi sintaks path relatif; kembalikan bagian-bagiannya."""
        if not isinstance(rel, str) or not rel or len(rel) > MAX_PATH_CHARS:
            raise WorkspaceError("Path kosong atau terlalu panjang")
        if "\x00" in rel or "\\" in rel or rel.startswith("/") or _DRIVE.match(rel):
            raise WorkspaceError(f"Path tidak diizinkan: {rel!r}")
        parts = rel.split("/")
        for part in parts:
            if part in {"", ".", ".."} or not _PART.match(part) or part.split(".")[0].lower() in _RESERVED:
                raise WorkspaceError(f"Bagian path tidak diizinkan: {part!r}")
        return parts

    def resolve(self, rel: str) -> Path:
        parts = self.check_relative(rel)
        path = self.root.joinpath(*parts)
        # resolve() mengikuti symlink/junction yang sudah ada; hasilnya wajib tetap di dalam root
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise WorkspaceError(f"Path keluar dari workspace: {rel!r}")
        return resolved

    # -- operasi -------------------------------------------------------------------

    def list(self) -> list[FileInfo]:
        out: list[FileInfo] = []
        if not self.root.exists():
            return out
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in _IGNORED_DIRS)
            for name in sorted(filenames):
                if name.startswith(".") or name.endswith(".pyc"):
                    continue
                full = Path(dirpath) / name
                if full.is_symlink():
                    continue
                out.append(FileInfo(full.relative_to(self.root).as_posix(), full.stat().st_size))
        return out

    def total_bytes(self) -> int:
        return sum(f.size for f in self.list())

    def exists(self, rel: str) -> bool:
        return self.resolve(rel).exists()

    def read(self, rel: str) -> str:
        path = self.resolve(rel)
        if not path.is_file():
            raise WorkspaceError(f"File tidak ditemukan: {rel}")
        if path.stat().st_size > MAX_FILE_BYTES * 4:
            raise WorkspaceError("File terlalu besar untuk dibaca")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise WorkspaceError("File bukan teks UTF-8") from e

    def write(self, rel: str, content: str, allowed_exts: set[str] = CODE_EXTS) -> tuple[bool, int]:
        """Tulis file secara atomik. Kembalikan (file_baru, jumlah_byte)."""
        path = self.resolve(rel)
        ext = path.suffix.lstrip(".").lower()
        if ext not in allowed_exts:
            raise WorkspaceError(f"Ekstensi .{ext or '(kosong)'} tidak diizinkan. Diizinkan: {', '.join(sorted(allowed_exts))}")
        if "\x00" in content:
            raise WorkspaceError("Isi file mengandung karakter NUL")
        data = content.replace("\r\n", "\n").encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise WorkspaceError(f"File melebihi batas {MAX_FILE_BYTES // 1000} KB: {rel}")
        existing = {f.path: f.size for f in self.list()}
        rel_norm = path.relative_to(self.root).as_posix()
        is_new = rel_norm not in existing
        if is_new and len(existing) >= MAX_FILES:
            raise WorkspaceError(f"Jumlah file melebihi batas {MAX_FILES}")
        if sum(existing.values()) - existing.get(rel_norm, 0) + len(data) > MAX_TOTAL_BYTES:
            raise WorkspaceError("Total ukuran workspace melebihi batas")
        if path.exists() and not path.is_file():
            raise WorkspaceError(f"Bukan file: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return is_new, len(data)

    def snapshot(self, budget_chars: int = 6000) -> str:
        """Ringkasan isi workspace untuk prompt: isi file sampai batas, sisanya hanya daftar path."""
        parts, used, hidden = [], 0, []
        for f in self.list():
            if f.path.endswith(".json") or f.size > budget_chars:
                hidden.append(f"{f.path} ({f.size} B)")
                continue
            try:
                text = self.read(f.path)
            except WorkspaceError:
                continue
            if used + len(text) > budget_chars:
                hidden.append(f"{f.path} ({f.size} B)")
                continue
            parts.append(f"### {f.path}\n{text}")
            used += len(text)
        if hidden:
            parts.append("[isi tidak ditampilkan karena batas konteks: " + ", ".join(hidden) + "]")
        return "\n\n".join(parts) if parts else "(workspace masih kosong)"
