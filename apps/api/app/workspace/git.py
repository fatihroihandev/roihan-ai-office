"""Riwayat perubahan workspace lewat Git (Bagian 13.3). Perintah git tetap berjalan di host dan hanya
menerima argumen dari kode kita (bukan dari agent); hook dimatikan agar isi workspace tidak dapat memicu eksekusi."""
import os
import re
import subprocess
from pathlib import Path

GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\n.junit.xml\n"
_BASE = ["git", "-c", "core.hooksPath=/dev/null/none", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false",
         "-c", "core.autocrlf=false", "-c", "gc.auto=0"]


class GitError(RuntimeError):
    pass


def _git(root: Path, *args: str, name: str = "Roihan Agent", email: str = "agent@roihan.local") -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    p = subprocess.run([*_BASE, *args], cwd=root, env=env, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise GitError(f"git {args[0]} gagal: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout.strip()


def ensure_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        _git(root, "init", "-q", "-b", "main")
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text(GITIGNORE, encoding="utf-8")


def head(root: Path) -> str | None:
    try:
        return _git(root, "rev-parse", "--short", "HEAD")
    except GitError:
        return None


def commit_all(root: Path, message: str, author: str = "Roihan Agent") -> str | None:
    """Commit semua perubahan. Kembalikan hash singkat, atau None jika tidak ada perubahan."""
    ensure_repo(root)
    _git(root, "add", "-A")
    if subprocess.run([*_BASE, "diff", "--cached", "--quiet"], cwd=root, capture_output=True).returncode == 0:
        return None
    _git(root, "commit", "-q", "-m", message[:200], name=author)
    return head(root)


def log(root: Path, limit: int = 20) -> list[dict]:
    if not (root / ".git").exists() or head(root) is None:
        return []
    out = _git(root, "log", f"-{limit}", "--pretty=format:%h%x1f%an%x1f%aI%x1f%s")
    rows = []
    for line in out.splitlines():
        h, author, when, subject = line.split("\x1f", 3)
        rows.append({"commit": h, "author": author, "date": when, "message": subject})
    return rows


def show(root: Path, sha: str, max_chars: int = 4000) -> str:
    """Ringkasan perubahan satu commit (stat + patch), dipotong. `sha` divalidasi agar hanya heksadesimal."""
    if not re.fullmatch(r"[0-9a-f]{4,40}", sha or ""):
        raise GitError("hash commit tidak valid")
    out = _git(root, "show", "--stat", "--patch", "--no-color", "--format=commit %h%n%s", sha)
    return out if len(out) <= max_chars else out[:max_chars] + "\n[...diff dipotong...]"
