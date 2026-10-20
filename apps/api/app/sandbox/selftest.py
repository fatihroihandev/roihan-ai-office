"""Uji isolasi sandbox (Bagian 14.2). Sandbox hanya dipakai jika semua uji lulus.

Setiap uji menjalankan kode Python kecil di dalam sandbox dan memeriksa bahwa pelanggaran yang dicoba GAGAL.
"""
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.sandbox.base import ExecResult, ExecSpec


@dataclass
class Case:
    name: str
    description: str
    code: str
    check: Callable[[ExecResult], bool]
    timeout_s: int = 20
    memory_mb: int = 256


def _out(r: ExecResult) -> str:
    return r.stdout.strip()


CASES = [
    Case("non_root", "Kode berjalan sebagai user biasa, bukan root",
         "import os; print(os.getuid())",
         lambda r: r.exit_code == 0 and _out(r).isdigit() and _out(r) != "0"),
    Case("no_network", "Tidak ada akses jaringan",
         "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), timeout=3); print('CONNECTED')\nexcept Exception:\n    print('BLOCKED')",
         lambda r: _out(r) == "BLOCKED"),
    Case("no_windows_drives", "Drive Windows tidak terlihat",
         "import os\nprint('VISIBLE' if (os.path.exists('/mnt/c/Windows') or (os.path.isdir('/mnt/c') and os.listdir('/mnt/c'))) else 'HIDDEN')",
         lambda r: _out(r) == "HIDDEN"),
    Case("cannot_write_system", "Tidak dapat menulis atau membaca area sistem",
         "res = []\nfor path, mode in (('/etc/rsh_probe', 'w'), ('/etc/shadow', 'r'), ('/root/.rsh_probe', 'w')):\n"
         "    try:\n        open(path, mode); res.append('OPENED')\n    except Exception:\n        res.append('DENIED')\nprint(','.join(res))",
         lambda r: _out(r) == "DENIED,DENIED,DENIED"),
    Case("memory_limit", "Alokasi memori berlebihan dihentikan",
         "try:\n    b = bytearray(2 * 1024 ** 3); print('ALLOCATED')\nexcept MemoryError:\n    print('LIMITED')",
         lambda r: "ALLOCATED" not in r.stdout),
    Case("timeout_kills_loop", "Proses yang tidak berhenti dimatikan oleh batas waktu",
         "while True:\n    pass",
         lambda r: r.timed_out and r.duration_ms < 30000, timeout_s=3),
    Case("env_clean", "Environment bersih: tidak mewarisi secret atau variabel Windows",
         "import os; print(' '.join(sorted(os.environ)))",
         lambda r: r.exit_code == 0 and not any(
             bad in r.stdout.upper() for bad in ("TOKEN", "KEY", "SECRET", "PASSWORD", "WSL", "WINDIR", "USERPROFILE", "APPDATA"))),
    # Interop WSL terdaftar di seluruh VM, jadi keberadaan entri binfmt_misc tidak membuktikan apa pun. Uji yang benar
    # adalah fungsional: jalankan program Windows sungguhan (whoami.exe milik host, hanya mencetak nama user) dari dalam
    # sandbox. Kontrol positif: di distro dengan interop aktif, uji ini mencetak DOMAIN\\user.
    Case("no_windows_interop", "Program Windows tidak dapat dijalankan dari sandbox (interop mati)",
         "import os, subprocess\n"
         "if not os.path.exists('probe.exe'):\n    print('NO_PROBE')\nelse:\n"
         "    os.chmod('probe.exe', 0o755)\n"
         "    try:\n"
         "        r = subprocess.run(['./probe.exe'], capture_output=True, text=True, timeout=40)\n"
         "        print('RAN' if '\\\\' in r.stdout else 'BLOCKED')\n"
         "    except Exception:\n        print('BLOCKED')",
         lambda r: _out(r) in {"BLOCKED", "NO_PROBE"}, timeout_s=60),
    Case("process_limit", "Jumlah proses dibatasi",
         "import resource; s, h = resource.getrlimit(resource.RLIMIT_NPROC); print(s)",
         lambda r: _out(r).isdigit() and 0 < int(_out(r)) <= 128),
    Case("isolated_pid_namespace", "Proses lain di distro tidak terlihat",
         "import os; print(len([p for p in os.listdir('/proc') if p.isdigit()]))",
         lambda r: _out(r).isdigit() and int(_out(r)) <= 5),
]


async def run_selftest(sandbox) -> dict:
    """`sandbox` harus menyediakan `run_unchecked(spec)`."""
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        (workspace / "marker.txt").write_text("selftest", encoding="utf-8")
        probe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe"
        if probe.is_file():  # biner Windows bawaan host yang tidak berbahaya (hanya mencetak nama user)
            (workspace / "probe.exe").write_bytes(probe.read_bytes())
        for case in CASES:
            spec = ExecSpec(["python3", "-c", case.code], workspace, timeout_s=case.timeout_s, memory_mb=case.memory_mb,
                            max_output_bytes=4096)
            try:
                result = await sandbox.run_unchecked(spec)
                ok, detail = bool(case.check(result)), (result.stdout.strip() or result.stderr.strip())[:200]
            except Exception as e:  # kegagalan infrastruktur dianggap uji gagal
                ok, detail = False, f"{type(e).__name__}: {e}"[:200]
            checks.append({"name": case.name, "description": case.description, "passed": ok, "detail": detail})
    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "ran_at": datetime.now(timezone.utc).isoformat()}
