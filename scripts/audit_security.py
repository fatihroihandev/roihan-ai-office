"""Audit keamanan otomatis (Fase 11). Jalankan dari akar repo: python scripts/audit_security.py [--deps]

Memeriksa: rahasia terlacak git, berkas yang wajib diabaikan, nilai bawaan aman di .env.example, token tidak bocor ke bundel
frontend, dan (opsional --deps) kerentanan dependensi produksi npm. Keluar dengan kode 1 bila ada temuan.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "kunci OpenAI/Anthropic": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "kunci Google API": re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    "token GitHub": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "kunci privat": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
# Fixture sengaja berisi pola rahasia palsu untuk menguji pemindai rahasia milik reviewer.
SCAN_EXEMPT = {"apps/api/tests/test_reviewer.py"}
MUST_IGNORE = [".env", "data/database/", "data/backups/", "data/projects/", "data/logs/", "*.db"]
TEXT_EXT = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".yml", ".yaml", ".toml", ".ini", ".env", ".example", ".css", ".sh", ".ps1", ".txt"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def check_tracked() -> list[str]:
    out: list[str] = []
    files = git("ls-files").splitlines()
    for f in files:
        name = Path(f).name
        if name == ".env" or (name.startswith(".env.") and not name.endswith(".example")) or f.endswith((".db", ".sqlite", ".pem", ".key")):
            out.append(f"berkas sensitif terlacak git: {f}")
        if f in SCAN_EXEMPT:
            continue
        p = ROOT / f
        if p.suffix.lower() not in TEXT_EXT and not name.endswith(".example") or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in SECRET_PATTERNS.items():
            if rx.search(text):
                out.append(f"{label} terdeteksi di {f}")
    return out


def check_gitignore() -> list[str]:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    return [f".gitignore tidak memuat '{p}'" for p in MUST_IGNORE if p not in text]


def check_env_example() -> list[str]:
    out: list[str] = []
    env = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("OPENAI_ENABLED", "GEMINI_ENABLED", "ANTHROPIC_ENABLED", "BUDGET_ALLOW_PAID_CALLS"):
        if env.get(k, "false").lower() != "false":
            out.append(f".env.example: {k} harus false secara bawaan")
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        if env.get(k):
            out.append(f".env.example: {k} harus kosong")
    for k in ("REQUIRE_APPROVAL_FOR_EXTERNAL_ACTIONS", "RESTRICT_WORKSPACE_ACCESS", "REDACT_SECRETS_IN_LOGS"):
        if env.get(k, "true").lower() != "true":
            out.append(f".env.example: {k} harus true secara bawaan")
    return out


def check_bundle_for_token() -> list[str]:
    """Token backend tidak boleh ada di bundel yang dikirim ke peramban (.next/static)."""
    static = ROOT / "apps" / "web" / ".next" / "static"
    if not static.exists():
        return []
    tokens = set()
    envf = ROOT / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            if line.startswith("APP_LOCAL_TOKEN=") and len(line.split("=", 1)[1].strip()) >= 16:
                tokens.add(line.split("=", 1)[1].strip())
    tokens.add("token-uji-1234567890")
    out = []
    for p in static.rglob("*"):
        if p.is_file() and p.suffix in {".js", ".css", ".html", ".json", ".map"}:
            data = p.read_text(encoding="utf-8", errors="ignore")
            for t in tokens:
                if t in data:
                    out.append(f"token backend ditemukan di bundel klien: {p.relative_to(ROOT)}")
    return out


def check_deps() -> list[str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return ["npm tidak ditemukan; audit dependensi dilewati"]
    r = subprocess.run([npm, "audit", "--omit=dev", "--audit-level=low"], cwd=ROOT / "apps" / "web", capture_output=True, text=True)
    return [] if r.returncode == 0 else ["npm audit (produksi) menemukan kerentanan:\n" + r.stdout.strip()]


def main() -> int:
    checks = {"rahasia terlacak": check_tracked, ".gitignore": check_gitignore, ".env.example": check_env_example,
              "bundel klien": check_bundle_for_token}
    if "--deps" in sys.argv:
        checks["dependensi npm (produksi)"] = check_deps
    findings = 0
    for name, fn in checks.items():
        res = fn()
        print(f"[{'LULUS' if not res else 'TEMUAN'}] {name}")
        for r in res:
            print("   -", r)
        findings += len(res)
    print(f"\n{findings} temuan")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
