"""Daftar perintah yang diizinkan (allowlist). Agent memilih jenis perintah dan path; argv dibentuk di sini."""
from dataclasses import dataclass

from app.workspace.files import WorkspaceError, WorkspaceFiles

JUNIT_FILE = ".junit.xml"
KINDS = ("pytest", "python_file", "compile")


class CommandError(ValueError):
    pass


@dataclass
class Command:
    kind: str
    argv: list[str]
    collect_file: str | None = None


def _existing(files: WorkspaceFiles, rel: str) -> str:
    try:
        path = files.resolve(rel)
    except WorkspaceError as e:
        raise CommandError(str(e)) from e
    if not path.exists():
        raise CommandError(f"Path tidak ditemukan di workspace: {rel}")
    return path.relative_to(files.root).as_posix()


def build_command(kind: str, args: list[str] | None, files: WorkspaceFiles) -> Command:
    args = list(args or [])
    if kind == "pytest":
        # Path dari agent divalidasi (tidak boleh diawali '-', tidak boleh keluar workspace); default: folder tests atau root
        paths = [_existing(files, a) for a in args] or (["tests"] if (files.root / "tests").is_dir() else [])
        base = ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", "--maxfail=25",
                f"--junitxml={JUNIT_FILE}"]
        return Command(kind, base + paths, JUNIT_FILE)
    if kind == "python_file":
        if len(args) != 1 or not args[0].endswith(".py"):
            raise CommandError("python_file memerlukan tepat satu file .py")
        return Command(kind, ["python3", _existing(files, args[0])])
    if kind == "compile":
        if args:
            raise CommandError("compile tidak menerima argumen")
        return Command(kind, ["python3", "-m", "compileall", "-q", "-f", "."])
    raise CommandError(f"Perintah tidak ada di allowlist: {kind!r}. Diizinkan: {', '.join(KINDS)}")
