import asyncio
import base64
import io
import shlex
import tarfile
from pathlib import Path

import pytest

from app.sandbox.base import DisabledSandbox, ExecSpec, SandboxUnavailable
from app.sandbox.factory import build_sandbox
from app.sandbox.selftest import CASES, run_selftest
from app.sandbox.wsl import (
    FILE_MARKER, INFRA_FAILURE, RawResult, WslSandbox, build_script, build_tar, parse_result,
)
from app.workspace.files import WorkspaceFiles


def run(coro):
    return asyncio.run(coro)


def spec(tmp_path, argv=None, **kw):
    return ExecSpec(argv or ["python3", "-m", "pytest"], tmp_path, **kw)


# ------------------------------------------------------------------ skrip isolasi

def test_script_contains_every_isolation_layer(tmp_path):
    s = build_script(spec(tmp_path, timeout_s=30, memory_mb=512))
    for part in ("unshare --net --pid --ipc --uts --fork --mount-proc --kill-child", "prlimit --as=536870912",
                 "--nproc=64", "--core=0", "--cpu=30", "setpriv --reuid=sandbox --regid=sandbox --clear-groups --no-new-privs",
                 "env -i HOME=", "timeout -k 2 30", "chmod 700", "trap 'rm -rf \"$D\"' EXIT", "tar -xf - -C"):
        assert part in s, part
    assert "/mnt/" not in s and "wsl.exe" not in s and "powershell" not in s.lower()


def test_argv_is_shell_quoted_so_injection_stays_literal(tmp_path):
    nasty = ["python3", "-c", "print(1); import os; os.system('rm -rf /')", "a b", "$(reboot)", "`id`", "x;y"]
    s = build_script(spec(tmp_path, argv=nasty))
    line = next(ln for ln in s.splitlines() if ln.strip().startswith("env -i"))
    tokens = shlex.split(line)
    assert tokens[-len(nasty):] == nasty            # tiap argumen tetap satu token utuh
    assert "$(reboot)" not in s.replace(shlex.quote("$(reboot)"), "")


@pytest.mark.parametrize("field,value", [("timeout_s", "1; reboot"), ("memory_mb", "64 && id"), ("timeout_s", "x")])
def test_numeric_limits_cannot_inject_commands(tmp_path, field, value):
    with pytest.raises(ValueError):
        build_script(spec(tmp_path, **{field: value}))


def test_collect_file_is_quoted(tmp_path):
    s = build_script(spec(tmp_path, collect_file=".junit.xml"))
    assert FILE_MARKER in s and "base64 -w0" in s and ".junit.xml" in s


# ------------------------------------------------------------------ tar workspace

def test_tar_contains_only_regular_workspace_files(tmp_path):
    ws = WorkspaceFiles(tmp_path / "src")
    ws.write("a.py", "x = 1\n")
    ws.write("pkg/b.py", "y = 2\n")
    (ws.root / ".git").mkdir()
    (ws.root / ".git" / "config").write_text("secret", encoding="utf-8")
    (ws.root / ".env").write_text("TOKEN=1", encoding="utf-8")
    names = {m.name: m for m in tarfile.open(fileobj=io.BytesIO(build_tar(ws)))}
    assert set(names) == {"a.py", "pkg/b.py"}
    assert all(m.isreg() and m.uid == 0 and m.mode == 0o644 for m in names.values())


def test_tar_rejects_oversized_workspace(tmp_path, monkeypatch):
    ws = WorkspaceFiles(tmp_path / "src")
    ws.write("a.txt", "x" * 100)
    monkeypatch.setattr("app.sandbox.wsl.MAX_TAR_BYTES", 10)
    with pytest.raises(SandboxUnavailable):
        build_tar(ws)


# ------------------------------------------------------------------ parsing hasil

def raw(rc=0, out=b"", err=b"", timed_out=False):
    return RawResult(rc, out, err, timed_out)


def test_parse_result_basic_and_truncation(tmp_path):
    r = parse_result(raw(1, b"halo", b"galat"), spec(tmp_path), 120)
    assert (r.exit_code, r.stdout, r.stderr, r.timed_out, r.output_truncated, r.duration_ms) == (1, "halo", "galat", False, False, 120)
    big = parse_result(raw(0, b"x" * 100), spec(tmp_path, max_output_bytes=10), 5)
    assert len(big.stdout) == 10 and big.output_truncated is True


def test_parse_result_collects_file_after_marker(tmp_path):
    payload = base64.b64encode("<testsuite/>".encode())
    r = parse_result(raw(0, b"1 passed\n" + FILE_MARKER.encode() + payload + b"\n"), spec(tmp_path), 5)
    assert r.collected == "<testsuite/>" and r.stdout.strip() == "1 passed"
    assert FILE_MARKER not in r.stdout


def test_parse_result_timeout_detection(tmp_path):
    assert parse_result(raw(None, timed_out=True), spec(tmp_path), 9000).timed_out is True
    s = spec(tmp_path, timeout_s=3)
    assert parse_result(raw(124), s, 3100).timed_out is True      # timeout(1) di dalam distro
    assert parse_result(raw(137), s, 3100).timed_out is True
    assert parse_result(raw(124), s, 200).timed_out is False       # exit 124 milik program, bukan timeout
    assert parse_result(raw(1), s, 3100).timed_out is False


def test_parse_result_infra_failure_raises(tmp_path):
    with pytest.raises(SandboxUnavailable) as e:
        parse_result(raw(INFRA_FAILURE, err=b"gagal mengekstrak workspace"), spec(tmp_path), 5)
    assert e.value.reason == "sandbox_infra_error" and "mengekstrak" in e.value.message


# ------------------------------------------------------------------ WslSandbox dengan runner palsu

class Runner:
    """Runner palsu: mencatat panggilan dan menjawab sesuai isi skrip."""

    def __init__(self, probe="OK", selftest_ok=True, probe_rc=0):
        self.calls = []
        self.probe, self.selftest_ok, self.probe_rc = probe, selftest_ok, probe_rc
        self.fail_case = None

    async def __call__(self, argv, stdin, timeout):
        self.calls.append((argv, stdin, timeout))
        script = argv[-1]
        if "id -u sandbox" in script:
            return RawResult(self.probe_rc, self.probe.encode(), b"")
        if "while True" in script:                       # loop tak berhenti: dimatikan oleh batas waktu
            return RawResult(None, b"", b"", timed_out=True)
        return RawResult(0, self._answer(script).encode(), b"")

    def _answer(self, script):
        good = {
            "os.getuid": "1000", "socket.create_connection": "BLOCKED", "/mnt/c/Windows": "HIDDEN",
            "/etc/rsh_probe": "DENIED,DENIED,DENIED", "bytearray": "LIMITED", "os.environ": "HOME LANG PATH",
            "RLIMIT_NPROC": "64", "/proc": "2",
        }
        for marker, answer in good.items():
            if marker in script:
                if self.fail_case and self.fail_case in script:
                    return {"os.getuid": "0", "socket.create_connection": "CONNECTED", "/mnt/c/Windows": "VISIBLE"}.get(marker, "BAD")
                return answer
        return ""   # while True: pass


def sandbox(runner=None, **kw):
    return WslSandbox("Ubuntu", runner=runner or Runner(**kw))


def test_distro_name_is_validated():
    for bad in ("", "a b", "x;rm", "../x", "a" * 65, "Ubu$ntu"):
        with pytest.raises(ValueError):
            WslSandbox(bad)
    assert WslSandbox("Ubuntu-24.04").distro == "Ubuntu-24.04"


def test_commands_target_the_dedicated_distro_via_exec(tmp_path):
    r = Runner()
    sb = sandbox(r)
    run(sb.basic_checks())
    argv = r.calls[0][0]
    assert argv[:7] == ["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "sh"] and argv[7] == "-c"


@pytest.mark.parametrize("probe,rc,reason", [
    ("NO_USER", 3, "sandbox_user_missing"), ("MISSING:unshare", 4, "sandbox_tool_missing"),
    ("INTEROP_ON", 5, "interop_enabled"), ("AUTOMOUNT_ON", 6, "automount_enabled"),
    ("", 1, "distro_unavailable"),
])
def test_basic_checks_report_actionable_reasons(probe, rc, reason):
    st = run(sandbox(probe=probe, probe_rc=rc).basic_checks())
    assert st.available is False and st.reason == reason and st.message


def test_basic_checks_wsl_missing_and_timeout():
    async def missing(argv, stdin, timeout):
        raise SandboxUnavailable("wsl_not_found", "wsl.exe tidak ditemukan")

    async def slow(argv, stdin, timeout):
        return RawResult(None, b"", b"", timed_out=True)
    assert run(sandbox(missing).basic_checks()).reason == "wsl_not_found"
    assert run(sandbox(slow).basic_checks()).reason == "wsl_timeout"


def test_run_is_refused_until_selftest_passes(tmp_path):
    ws = WorkspaceFiles(tmp_path / "src")
    ws.write("a.py", "x = 1\n")
    sb = sandbox()
    with pytest.raises(SandboxUnavailable) as e:
        run(sb.run(ExecSpec(["python3", "a.py"], ws.root)))
    assert e.value.reason == "isolation_not_verified"


def test_status_runs_selftest_once_and_becomes_available(tmp_path):
    r = Runner()
    sb = sandbox(r)
    st = run(sb.status())
    assert st.available is True and st.details["selftest"]["passed"] is True
    calls_after_first = len(r.calls)
    run(sb.status())
    assert len(r.calls) == calls_after_first + 1          # hanya pemeriksaan dasar; selftest tidak diulang
    ws = WorkspaceFiles(tmp_path / "src")
    ws.write("a.py", "x = 1\n")
    res = run(sb.run(ExecSpec(["python3", "a.py"], ws.root)))
    assert res.exit_code == 0
    argv, stdin, timeout = r.calls[-1]
    assert tarfile.open(fileobj=io.BytesIO(stdin)).getnames() == ["a.py"] and timeout == 60 + 20


@pytest.mark.parametrize("fail", ["os.getuid", "socket.create_connection", "/mnt/c/Windows"])
def test_failed_isolation_check_makes_sandbox_unavailable(fail):
    r = Runner()
    r.fail_case = fail
    st = run(sandbox(r).status())
    assert st.available is False and st.reason == "isolation_selftest_failed"
    assert any(not c["passed"] for c in st.details["selftest"]["checks"])


def test_selftest_covers_the_documented_risk_areas():
    names = {c.name for c in CASES}
    assert {"non_root", "no_network", "no_windows_drives", "cannot_write_system", "memory_limit",
            "timeout_kills_loop", "env_clean", "process_limit"} <= names


def test_selftest_treats_exceptions_as_failures():
    class Boom:
        async def run_unchecked(self, spec):
            raise RuntimeError("wsl mati")
    report = run(run_selftest(Boom()))
    assert report["passed"] is False and all("RuntimeError" in c["detail"] for c in report["checks"])


def test_env_check_flags_leaked_secrets():
    class Leaky:
        async def run_unchecked(self, spec):
            from app.sandbox.base import ExecResult
            return ExecResult(0, "HOME APP_LOCAL_TOKEN PATH", "", 5)
    report = run(run_selftest(Leaky()))
    assert next(c for c in report["checks"] if c["name"] == "env_clean")["passed"] is False


def test_disabled_sandbox_refuses_everything(tmp_path):
    sb = DisabledSandbox()
    st = run(sb.status())
    assert (st.available, st.reason) == (False, "sandbox_disabled")
    with pytest.raises(SandboxUnavailable):
        run(sb.run(ExecSpec(["python3", "-c", "print(1)"], Path(tmp_path))))


def test_factory_follows_settings(settings):
    assert isinstance(build_sandbox(settings), DisabledSandbox)
    wsl = build_sandbox(settings.model_copy(update={"sandbox_backend": "wsl", "sandbox_wsl_distro": "Debian"}))
    assert isinstance(wsl, WslSandbox) and wsl.distro == "Debian"


def test_basic_checks_script_verifies_interop_and_drive_mounts_outside_the_sandbox():
    r = Runner()
    run(sandbox(r).basic_checks())
    script = r.calls[0][0][-1]
    assert "wslinterop" in script and "binfmt_misc" in script and "/proc/mounts" in script and "/mnt/[a-z]" in script


def test_interop_or_automount_makes_sandbox_unavailable_without_running_selftest():
    for probe, rc, reason in (("INTEROP_ON", 5, "interop_enabled"), ("AUTOMOUNT_ON", 6, "automount_enabled")):
        r = Runner(probe=probe, probe_rc=rc)
        st = run(sandbox(r).status())
        assert (st.available, st.reason) == (False, reason)
        assert len(r.calls) == 1                         # berhenti di pemeriksaan dasar; kode tidak dijalankan
