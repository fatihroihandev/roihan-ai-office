"""Kontrak sandbox (Bagian 14). Agent tidak pernah memanggil `run` dengan argv bebas: argv selalu dibentuk
oleh `commands.build_command` dari daftar perintah yang diizinkan. `run` sendiri adalah API internal."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class SandboxUnavailable(Exception):
    """Sandbox tidak tersedia atau belum lolos uji isolasi; eksekusi tidak boleh dilakukan."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class ExecSpec:
    argv: list[str]
    workspace: Path
    timeout_s: int = 60
    memory_mb: int = 768
    max_output_bytes: int = 64 * 1024
    collect_file: str | None = None  # file hasil perintah (mis. laporan JUnit) yang diambil kembali, relatif terhadap workspace


@dataclass
class ExecResult:
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    output_truncated: bool = False
    collected: str | None = None  # isi collect_file jika ada


@dataclass
class SandboxStatus:
    available: bool
    backend: str
    reason: str | None = None          # kode alasan jika tidak tersedia
    message: str | None = None
    details: dict = field(default_factory=dict)


class Sandbox(ABC):
    name: str

    @abstractmethod
    async def status(self) -> SandboxStatus: ...

    @abstractmethod
    async def run(self, spec: ExecSpec) -> ExecResult: ...

    async def selftest(self) -> dict:
        """Jalankan uji isolasi. Implementasi default: tidak ada uji (sandbox nonaktif)."""
        return {"passed": False, "checks": [], "ran_at": None}


class DisabledSandbox(Sandbox):
    """Tidak ada isolasi yang tersedia: semua eksekusi ditolak (tidak ada jalan pintas ke subprocess biasa)."""

    name = "none"

    def __init__(self, message: str = "Sandbox belum dikonfigurasi (SANDBOX_BACKEND=none)"):
        self._message = message

    async def status(self) -> SandboxStatus:
        return SandboxStatus(False, self.name, "sandbox_disabled", self._message)

    async def run(self, spec: ExecSpec) -> ExecResult:
        raise SandboxUnavailable("sandbox_disabled", self._message)
