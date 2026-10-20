import pytest

from app.sandbox.commands import JUNIT_FILE, CommandError, build_command
from app.workspace.files import WorkspaceFiles


@pytest.fixture
def ws(tmp_path):
    w = WorkspaceFiles(tmp_path / "src")
    w.write("calc.py", "def add(a, b):\n    return a + b\n")
    w.write("tests/test_calc.py", "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    return w


def test_pytest_defaults_to_tests_dir_and_collects_junit(ws):
    c = build_command("pytest", None, ws)
    assert c.argv[:4] == ["python3", "-m", "pytest", "-q"] and c.argv[-1] == "tests"
    assert f"--junitxml={JUNIT_FILE}" in c.argv and "-p" in c.argv and "no:cacheprovider" in c.argv
    assert c.collect_file == JUNIT_FILE


def test_pytest_without_tests_dir_runs_from_root(tmp_path):
    w = WorkspaceFiles(tmp_path / "src")
    w.write("test_x.py", "def test_x():\n    pass\n")
    assert build_command("pytest", [], w).argv[-1].startswith("--junitxml")


def test_pytest_accepts_existing_relative_paths(ws):
    assert build_command("pytest", ["tests/test_calc.py"], ws).argv[-1] == "tests/test_calc.py"


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "tests/nope.py", "-k", "--rootdir=/", ".git", "a b", "tests\\test_calc.py"])
def test_pytest_rejects_unsafe_or_missing_paths(ws, bad):
    with pytest.raises(CommandError):
        build_command("pytest", [bad], ws)


def test_python_file_and_compile(ws):
    assert build_command("python_file", ["calc.py"], ws).argv == ["python3", "calc.py"]
    assert build_command("compile", None, ws).argv == ["python3", "-m", "compileall", "-q", "-f", "."]
    for args in ([], ["calc.py", "extra"], ["tests"], ["missing.py"], ["../calc.py"]):
        with pytest.raises(CommandError):
            build_command("python_file", args, ws)
    with pytest.raises(CommandError):
        build_command("compile", ["x"], ws)


@pytest.mark.parametrize("kind", ["bash", "sh", "pip", "pip install requests", "curl", "rm", "python3", "node", "npm", "git", "", "PYTEST"])
def test_everything_outside_allowlist_is_rejected(ws, kind):
    with pytest.raises(CommandError) as e:
        build_command(kind, ["calc.py"], ws)
    assert "allowlist" in str(e.value)
