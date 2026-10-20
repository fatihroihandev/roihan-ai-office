import os

import pytest

from app.workspace.files import MAX_FILE_BYTES, MAX_FILES, WorkspaceError, WorkspaceFiles


@pytest.fixture
def ws(tmp_path):
    return WorkspaceFiles(tmp_path / "source-code")


@pytest.mark.parametrize("rel", [
    "", "/etc/passwd", "../x.py", "a/../../x.py", "a/./b.py", "a//b.py", "C:/Windows/x.py", "c:x.py", "a\\b.py",
    ".git/config", ".env", "src/.hidden.py", "nul.py", "CON.txt", "com1.md", "a b.py", "x" * 201 + ".py", "a/b/",
    "naïve.py", "x\x00.py", "-rf.py",
])
def test_unsafe_paths_are_rejected(ws, rel):
    with pytest.raises(WorkspaceError):
        ws.write(rel, "x")
    assert ws.list() == []


def test_write_read_roundtrip_and_atomic(ws):
    assert ws.write("pkg/mod.py", "a = 1\r\nb = 2\r\n") == (True, 12)
    assert ws.read("pkg/mod.py") == "a = 1\nb = 2\n"
    assert ws.write("pkg/mod.py", "a = 3\n") == (False, 6)
    assert [f.path for f in ws.list()] == ["pkg/mod.py"]
    assert not list(ws.root.rglob("*.tmp"))


@pytest.mark.parametrize("name", ["run.exe", "x.sh", "x.bat", "x.js", "x.html", "x.svg", "x.pyc", "noext"])
def test_disallowed_extensions(ws, name):
    with pytest.raises(WorkspaceError):
        ws.write(name, "x")


def test_doc_only_extensions(ws):
    ws.write("docs/a.md", "# a", {"md", "txt"})
    with pytest.raises(WorkspaceError):
        ws.write("a.py", "x", {"md", "txt"})


def test_size_and_count_limits(ws):
    with pytest.raises(WorkspaceError):
        ws.write("big.txt", "x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(WorkspaceError):
        ws.write("nul.txt", "a\x00b")
    for i in range(MAX_FILES):
        ws.write(f"f{i}.txt", "x")
    with pytest.raises(WorkspaceError):
        ws.write("one_more.txt", "x")
    ws.write("f0.txt", "dimodifikasi")  # menimpa file yang ada tetap boleh


def test_total_size_limit(ws, monkeypatch):
    monkeypatch.setattr("app.workspace.files.MAX_TOTAL_BYTES", 100)
    ws.write("a.txt", "x" * 60)
    with pytest.raises(WorkspaceError):
        ws.write("b.txt", "x" * 60)


def test_symlink_escape_is_blocked(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("rahasia", encoding="utf-8")
    ws.root.mkdir(parents=True)
    try:
        os.symlink(outside, ws.root / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink tidak dapat dibuat pada sistem ini")
    with pytest.raises(WorkspaceError):
        ws.read("link/secret.txt")
    with pytest.raises(WorkspaceError):
        ws.write("link/new.txt", "x")
    assert not (outside / "new.txt").exists()
    assert ws.list() == []        # symlink tidak ikut terdaftar


def test_list_skips_hidden_and_cache(ws):
    ws.write("a.py", "x")
    (ws.root / ".git").mkdir()
    (ws.root / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (ws.root / "__pycache__").mkdir()
    (ws.root / "__pycache__" / "a.cpython.pyc").write_bytes(b"\x00")
    (ws.root / ".env").write_text("SECRET=1", encoding="utf-8")
    assert [f.path for f in ws.list()] == ["a.py"]


def test_read_errors(ws):
    ws.write("a.py", "x")
    (ws.root / "bin.txt").write_bytes(b"\xff\xfe\x80")
    with pytest.raises(WorkspaceError):
        ws.read("missing.py")
    with pytest.raises(WorkspaceError):
        ws.read("bin.txt")
    with pytest.raises(WorkspaceError):
        ws.read("../a.py")


def test_snapshot_respects_budget_and_lists_hidden_files(ws):
    ws.write("a.py", "x" * 50)
    ws.write("b.py", "y" * 5000)
    ws.write("data.json", "{}")
    snap = ws.snapshot(budget_chars=100)
    assert "### a.py" in snap and "b.py (5000 B)" in snap and "data.json (2 B)" in snap and "### b.py" not in snap
    assert WorkspaceFiles(ws.root.parent / "kosong").snapshot() == "(workspace masih kosong)"
