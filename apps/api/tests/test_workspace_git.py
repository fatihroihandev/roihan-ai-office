import subprocess

import pytest

from app.workspace import git


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "source-code"
    git.ensure_repo(r)
    return r


def test_ensure_repo_is_idempotent_and_ignores_caches(root):
    git.ensure_repo(root)
    assert (root / ".git").is_dir()
    assert "__pycache__/" in (root / ".gitignore").read_text(encoding="utf-8")
    assert git.head(root) is None and git.log(root) == []


def test_commit_all_records_author_and_skips_empty_commits(root):
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    sha = git.commit_all(root, "Tambah a.py", author="developer agent")
    assert sha and git.head(root) == sha
    assert git.commit_all(root, "tanpa perubahan") is None
    (root / "a.py").write_text("x = 2\n", encoding="utf-8")
    git.commit_all(root, "Ubah a.py", author="qa agent")
    log = git.log(root)
    assert [(c["message"], c["author"]) for c in log] == [("Ubah a.py", "qa agent"), ("Tambah a.py", "developer agent")]


def test_ignored_files_are_not_committed(root):
    (root / "a.py").write_text("x", encoding="utf-8")
    (root / ".pytest_cache").mkdir()
    (root / ".pytest_cache" / "v").write_text("x", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    git.commit_all(root, "c")
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.split()
    assert sorted(tracked) == [".gitignore", "a.py"]


def test_hooks_never_run(root):
    marker = root.parent / "hook-ran"
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch '{marker.as_posix()}'\n", encoding="utf-8")
    hook.chmod(0o755)
    (root / "a.py").write_text("x", encoding="utf-8")
    assert git.commit_all(root, "dengan hook jahat")
    assert not marker.exists()
