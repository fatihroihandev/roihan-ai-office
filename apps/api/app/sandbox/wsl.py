"""Sandbox berbasis distro WSL2 khusus (Bagian 14.2).

Lapisan isolasi per eksekusi (semua di dalam distro, dijalankan sebagai root lalu menurunkan hak):
  - folder kerja sementara di dalam distro; workspace disalin masuk lewat tar (stdin) dan tidak ada akses ke drive Windows
  - namespace jaringan kosong (`unshare --net`): tanpa jaringan; namespace PID/IPC/UTS terpisah
  - user biasa `sandbox` (setpriv, no-new-privs) dengan environment kosong (`env -i`): tidak mewarisi secret
  - batas memori, jumlah proses, ukuran file, dan CPU (`prlimit`), serta batas waktu (`timeout`)
Distro disiapkan oleh scripts/setup_sandbox_wsl.sh dan hanya dipakai jika uji isolasi (selftest) lulus.
"""
import asyncio
import base64
import io
import logging
import re
import shlex
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.sandbox.base import ExecResult, ExecSpec, Sandbox, SandboxStatus, SandboxUnavailable
from app.sandbox.selftest import run_selftest
from app.workspace.files import WorkspaceFiles

logger = logging.getLogger("roihan.sandbox")

SANDBOX_USER = "sandbox"
FILE_MARKER = "@@RSH-FILE@@"
INFRA_FAILURE = 125
MAX_TAR_BYTES = 5 * 1024 * 1024
MAX_COLLECT_BYTES = 500_000
HARD_OUTPUT_CAP = 2 * 1024 * 1024
REQUIRED_TOOLS = ("unshare", "prlimit", "setpriv", "timeout", "tar", "base64", "python3")


@dataclass
class RawResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


async def default_runner(argv: list[str], stdin: bytes | None, timeout: float) -> RawResult:
    """Jalankan wsl.exe dan kumpulkan keluaran dengan batas ukuran; matikan jika melewati batas waktu."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError as e:
        raise SandboxUnavailable("wsl_not_found", "wsl.exe tidak ditemukan") from e

    async def read(stream) -> bytes:
        buf = bytearray()
        while chunk := await stream.read(65536):
            if len(buf) < HARD_OUTPUT_CAP:
                buf += chunk[: HARD_OUTPUT_CAP - len(buf)]
        return bytes(buf)

    async def feed():
        if stdin is not None and proc.stdin is not None:
            try:
                proc.stdin.write(stdin)
                await proc.stdin.drain()
                proc.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

    try:
        out, err, _ = await asyncio.wait_for(asyncio.gather(read(proc.stdout), read(proc.stderr), feed()), timeout)
        await proc.wait()
        return RawResult(proc.returncode, out, err)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return RawResult(None, b"", b"", timed_out=True)


def build_tar(files: WorkspaceFiles) -> bytes:
    """Arsip berisi file reguler workspace saja (tanpa symlink, tanpa folder tersembunyi seperti .git)."""
    buf = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for f in files.list():
            path = files.resolve(f.path)
            data = path.read_bytes()
            total += len(data)
            if total > MAX_TAR_BYTES:
                raise SandboxUnavailable("workspace_too_large", "Workspace terlalu besar untuk disalin ke sandbox")
            info = tarfile.TarInfo(f.path)
            info.size, info.mode, info.uid, info.gid, info.mtime = len(data), 0o644, 0, 0, int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def build_script(spec: ExecSpec) -> str:
    """Skrip sh yang dijalankan di dalam distro. Semua nilai numerik dipaksa int; argv di-quote."""
    timeout = int(spec.timeout_s)
    as_bytes = int(spec.memory_mb) * 1024 * 1024
    argv = " ".join(shlex.quote(a) for a in spec.argv)
    collect = ""
    if spec.collect_file:
        f = shlex.quote(spec.collect_file)
        collect = (f'if [ -f "$D"/{f} ]; then printf "\\n{FILE_MARKER}"; '
                   f'head -c {MAX_COLLECT_BYTES} "$D"/{f} | base64 -w0; printf "\\n"; fi\n')
    return f"""set -u
D=$(mktemp -d /var/tmp/rsh.XXXXXXXX) || exit {INFRA_FAILURE}
trap 'rm -rf "$D"' EXIT
chmod 700 "$D"
tar -xf - -C "$D" --no-same-owner --no-same-permissions 2>/dev/null || {{ echo "gagal mengekstrak workspace" >&2; exit {INFRA_FAILURE}; }}
chown -R {SANDBOX_USER}:{SANDBOX_USER} "$D"
cd "$D"
timeout -k 2 {timeout} unshare --net --pid --ipc --uts --fork --mount-proc --kill-child -- \\
  prlimit --as={as_bytes} --nproc=64 --fsize=20000000 --nofile=256 --core=0 --cpu={timeout} -- \\
  setpriv --reuid={SANDBOX_USER} --regid={SANDBOX_USER} --clear-groups --no-new-privs -- \\
  env -i HOME="$D" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 {argv}
rc=$?
{collect}exit $rc
"""


def _decode(data: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(data) > limit
    return data[:limit].decode("utf-8", errors="replace"), truncated


def parse_result(raw: RawResult, spec: ExecSpec, duration_ms: int) -> ExecResult:
    if raw.timed_out:
        return ExecResult(None, "", "", duration_ms, timed_out=True)
    if raw.returncode == INFRA_FAILURE:
        raise SandboxUnavailable("sandbox_infra_error", (raw.stderr.decode("utf-8", "replace") or "kegagalan infrastruktur sandbox").strip()[:300])
    out, err = raw.stdout, raw.stderr
    collected = None
    idx = out.rfind(FILE_MARKER.encode())
    if idx >= 0:
        tail = out[idx + len(FILE_MARKER):].strip()
        out = out[:idx]
        try:
            collected = base64.b64decode(tail, validate=False).decode("utf-8", "replace")
        except Exception:
            collected = None
    stdout, t1 = _decode(out, spec.max_output_bytes)
    stderr, t2 = _decode(err, spec.max_output_bytes)
    timed_out = raw.returncode in (124, 137) and duration_ms >= spec.timeout_s * 1000 - 500
    return ExecResult(raw.returncode, stdout, stderr, duration_ms, timed_out, t1 or t2, collected)


class WslSandbox(Sandbox):
    name = "wsl"

    def __init__(self, distro: str, runner=default_runner, wsl_exe: str = "wsl.exe"):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", distro):
            raise ValueError("Nama distro WSL tidak valid")
        self.distro = distro
        self._runner = runner
        self._wsl = wsl_exe
        self._report: dict | None = None  # hasil selftest terakhir (disimpan selama proses hidup)
        self._lock = asyncio.Lock()

    def _argv(self, script: str) -> list[str]:
        """wsl.exe mem-parse ulang baris perintah (tanda kutip ganda dan baris baru mudah rusak). Karena itu skrip
        dikirim sebagai base64 (hanya [A-Za-z0-9+/=]) dan dijalankan dengan `exec sh`, sehingga stdin tetap utuh
        untuk arsip workspace."""
        # Berkas skrip sementara menghapus dirinya sendiri pada baris pertama (berlaku untuk semua skrip, termasuk probe)
        b64 = base64.b64encode(('rm -f "$0"\n' + script).encode()).decode()
        loader = f"f=$(mktemp);printf %s {b64}|base64 -d>$f;exec sh $f"
        return [self._wsl, "-d", self.distro, "-u", "root", "--exec", "sh", "-c", loader]

    async def _probe(self, script: str, timeout: float = 30) -> RawResult:
        return await self._runner(self._argv(script), None, timeout)

    async def basic_checks(self) -> SandboxStatus:
        """Pemeriksaan ringan: distro ada, user sandbox ada, alat isolasi tersedia."""
        try:
            raw = await self._probe(
                f"id -u {SANDBOX_USER} >/dev/null 2>&1 || {{ echo NO_USER; exit 3; }}; "
                + "; ".join(f"command -v {t} >/dev/null 2>&1 || {{ echo MISSING:{t}; exit 4; }}" for t in REQUIRED_TOOLS)
                # Drive Windows (drvfs/9p) dapat dibaca dan ditulis oleh user Linux mana pun bila ter-mount.
                + "; grep -qE ' /mnt/[a-z] ' /proc/mounts && { echo AUTOMOUNT_ON; exit 6; }"
                + "; echo OK")
        except SandboxUnavailable as e:
            return SandboxStatus(False, self.name, e.reason, e.message)
        if raw.timed_out:
            return SandboxStatus(False, self.name, "wsl_timeout", "WSL tidak merespons")
        text = raw.stdout.decode("utf-8", "replace").strip()
        if raw.returncode == 0 and text.endswith("OK"):
            return SandboxStatus(True, self.name, details={"distro": self.distro})
        if "NO_USER" in text:
            return SandboxStatus(False, self.name, "sandbox_user_missing",
                                 f"User '{SANDBOX_USER}' belum ada di distro {self.distro}. Jalankan scripts/setup_sandbox_wsl.ps1")
        if "AUTOMOUNT_ON" in text:
            return SandboxStatus(False, self.name, "automount_enabled",
                                 f"Drive Windows ter-mount di distro {self.distro}; jalankan scripts/setup_sandbox_wsl.ps1")
        if "MISSING:" in text:
            return SandboxStatus(False, self.name, "sandbox_tool_missing", f"Alat belum terpasang di distro: {text.split('MISSING:')[-1]}")
        err = (raw.stderr.decode("utf-16-le", "ignore") if raw.stderr[:2] in (b"\xff\xfe",) or b"\x00" in raw.stderr[:8]
               else raw.stderr.decode("utf-8", "replace")).replace("\x00", "").strip()
        return SandboxStatus(False, self.name, "distro_unavailable", (err or f"Distro WSL '{self.distro}' tidak dapat dijalankan")[:300])

    async def selftest(self) -> dict:
        async with self._lock:
            self._report = await run_selftest(self)
            return self._report

    async def status(self) -> SandboxStatus:
        basic = await self.basic_checks()
        if not basic.available:
            return basic
        if self._report is None:
            await self.selftest()
        assert self._report is not None
        if not self._report["passed"]:
            failed = [c["name"] for c in self._report["checks"] if not c["passed"]]
            return SandboxStatus(False, self.name, "isolation_selftest_failed",
                                 "Uji isolasi sandbox gagal: " + ", ".join(failed), {"selftest": self._report})
        return SandboxStatus(True, self.name, details={"distro": self.distro, "selftest": self._report})

    async def run(self, spec: ExecSpec) -> ExecResult:
        # Pertahanan berlapis: tanpa uji isolasi yang lulus, tidak ada kode yang boleh dijalankan
        if not (self._report and self._report["passed"]):
            raise SandboxUnavailable("isolation_not_verified", "Uji isolasi sandbox belum lulus; eksekusi ditolak")
        return await self.run_unchecked(spec)

    async def run_unchecked(self, spec: ExecSpec) -> ExecResult:
        """Dipakai selftest sebelum sandbox dinyatakan lolos. Agent tidak pernah memanggil ini."""
        files = WorkspaceFiles(spec.workspace)
        tar_bytes = build_tar(files)
        script = build_script(spec)
        start = time.perf_counter()
        raw = await self._runner(self._argv(script), tar_bytes, spec.timeout_s + 20)
        return parse_result(raw, spec, int((time.perf_counter() - start) * 1000))
