import pytest

from app.projects.uploads import FileKind, UploadError, sanitize_filename, validate_upload

MB = 1024 * 1024


@pytest.mark.parametrize("raw,expected", [
    ("spec.md", "spec.md"),
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\windows\\win.ini.txt", "win.ini.txt"),
    ("my spec (final).md", "my_spec__final_.md"),
    (".hidden.md", "hidden.md"),
])
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "CON.txt", "nul.md", "../", "..."])
def test_sanitize_rejects_invalid(raw):
    with pytest.raises(UploadError):
        sanitize_filename(raw)


def test_sanitize_limits_length():
    name = sanitize_filename("a" * 300 + ".md")
    assert len(name) <= 100 and name.endswith(".md")


def ok(kind, name, data):
    return validate_upload(kind, name, data, MB)


def test_master_must_be_markdown():
    assert ok(FileKind.master, "MASTER.md", b"# Judul")[1] == "text/markdown"
    with pytest.raises(UploadError):
        ok(FileKind.master, "MASTER.pdf", b"%PDF-1.4")


@pytest.mark.parametrize("name", ["run.exe", "x.py", "x.js", "x.sh", "x.bat", "x.php", "x.html", "x.svg", "x.zip", "x"])
def test_dangerous_extensions_rejected(name):
    for kind in FileKind:
        with pytest.raises(UploadError):
            ok(kind, name, b"data")


def test_content_must_match_extension():
    with pytest.raises(UploadError):
        ok(FileKind.reference, "fake.png", b"bukan png")
    with pytest.raises(UploadError):
        ok(FileKind.reference, "fake.pdf", b"bukan pdf")
    with pytest.raises(UploadError):
        ok(FileKind.reference, "bin.txt", b"abc\x00def")
    with pytest.raises(UploadError):
        ok(FileKind.reference, "latin.txt", b"\xff\xfe\x80")


def test_valid_binary_types():
    assert ok(FileKind.reference, "a.png", b"\x89PNG\r\n\x1a\n....")[1] == "image/png"
    assert ok(FileKind.reference, "a.jpg", b"\xff\xd8\xff\xe0....")[1] == "image/jpeg"
    assert ok(FileKind.requirement, "a.pdf", b"%PDF-1.7 ...")[1] == "application/pdf"
    assert ok(FileKind.requirement, "a.docx", b"PK\x03\x04....")[1].endswith("wordprocessingml.document")
    assert ok(FileKind.reference, "a.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ")[1] == "image/webp"


def test_size_and_empty():
    with pytest.raises(UploadError) as e:
        validate_upload(FileKind.reference, "a.txt", b"x" * (MB + 1), MB)
    assert e.value.status == 413
    with pytest.raises(UploadError):
        ok(FileKind.reference, "a.txt", b"")
