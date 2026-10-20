import hashlib
import json

from sqlalchemy import select

from app.db.models import AuditLog


def create(client, auth, name="Proyek A", **kw):
    r = client.post("/api/projects", json={"name": name, **kw}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, auth, pid, name="spec.md", content=b"# Spec", kind="requirement", ctype="text/markdown"):
    return client.post(f"/api/projects/{pid}/files", headers=auth, data={"kind": kind},
                       files={"file": (name, content, ctype)})


def test_all_endpoints_require_token(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "x"}).status_code == 401
    assert client.get("/api/projects/abc/files").status_code == 401
    assert client.post("/api/projects/abc/files", data={"kind": "asset"}).status_code == 401


def test_create_builds_storage_layout_and_metadata(client, auth, settings):
    p = create(client, auth, "  Roihan CRM  ", description="Aplikasi internal")
    assert p["name"] == "Roihan CRM" and p["status"] == "active"
    base = settings.projects_dir / p["id"]
    for sub in ["input/requirements", "input/references", "input/assets", "workspace/source-code",
                "artifacts", "reports", "metadata"]:
        assert (base / sub).is_dir(), sub
    meta = json.loads((base / "metadata" / "project.json").read_text(encoding="utf-8"))
    assert meta["id"] == p["id"] and meta["name"] == "Roihan CRM"


def test_create_validation(client, auth):
    assert client.post("/api/projects", json={"name": "   "}, headers=auth).status_code == 422
    assert client.post("/api/projects", json={"name": "x" * 121}, headers=auth).status_code == 422
    assert client.post("/api/projects", json={}, headers=auth).status_code == 422


def test_list_get_update(client, auth):
    a, b = create(client, auth, "A"), create(client, auth, "B")
    ids = [p["id"] for p in client.get("/api/projects", headers=auth).json()]
    assert set(ids) == {a["id"], b["id"]}

    assert client.get(f"/api/projects/{a['id']}", headers=auth).json()["name"] == "A"
    r = client.patch(f"/api/projects/{a['id']}", json={"name": "A2", "status": "archived"}, headers=auth)
    assert r.json()["name"] == "A2" and r.json()["status"] == "archived"
    archived = client.get("/api/projects?status=archived", headers=auth).json()
    assert [p["id"] for p in archived] == [a["id"]]
    assert client.patch(f"/api/projects/{a['id']}", json={"status": "bogus"}, headers=auth).status_code == 422
    assert client.get("/api/projects/tidak-ada", headers=auth).status_code == 404


def test_delete_is_soft_and_keeps_files_on_disk(client, auth, settings):
    p = create(client, auth)
    up = upload(client, auth, p["id"])
    assert up.status_code == 201
    on_disk = settings.projects_dir / p["id"] / up.json()["relative_path"]

    assert client.delete(f"/api/projects/{p['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/projects/{p['id']}", headers=auth).status_code == 404
    assert client.get("/api/projects", headers=auth).json() == []
    assert on_disk.is_file()


def test_upload_stores_in_input_and_records_hash(client, auth, settings):
    p = create(client, auth)
    content = b"# Master doc"
    r = upload(client, auth, p["id"], "MASTER_DEVELOPMENT.md", content, kind="master")
    assert r.status_code == 201
    body = r.json()
    assert body["relative_path"] == "input/MASTER_DEVELOPMENT.md"
    assert body["sha256"] == hashlib.sha256(content).hexdigest() and body["size_bytes"] == len(content)
    assert (settings.projects_dir / p["id"] / body["relative_path"]).read_bytes() == content

    r2 = upload(client, auth, p["id"], "brief.md", b"x", kind="reference")
    assert r2.json()["relative_path"] == "input/references/brief.md"


def test_upload_never_overwrites_and_never_touches_workspace(client, auth, settings):
    p = create(client, auth)
    first = upload(client, auth, p["id"], "a.md", b"satu").json()
    second = upload(client, auth, p["id"], "a.md", b"dua").json()
    assert first["stored_name"] == "a.md" and second["stored_name"] == "a-2.md"
    base = settings.projects_dir / p["id"]
    assert (base / first["relative_path"]).read_bytes() == b"satu"
    assert (base / second["relative_path"]).read_bytes() == b"dua"
    assert list((base / "workspace").rglob("*.md")) == []


def test_upload_path_traversal_is_neutralised(client, auth, settings):
    p = create(client, auth)
    r = upload(client, auth, p["id"], "../../../evil.md", b"x")
    assert r.status_code == 201
    assert r.json()["relative_path"] == "input/requirements/evil.md"
    assert not (settings.data_dir / "evil.md").exists() and not (settings.projects_dir / "evil.md").exists()


def test_upload_rejections(client, auth):
    p = create(client, auth)
    assert upload(client, auth, p["id"], "run.exe", b"MZ").status_code == 422
    assert upload(client, auth, p["id"], "fake.png", b"bukan png", kind="reference").status_code == 422
    assert upload(client, auth, p["id"], "spec.pdf", b"%PDF-1.4", kind="master").status_code == 422
    assert upload(client, auth, p["id"], "empty.md", b"").status_code == 422
    assert upload(client, auth, p["id"], "a.md", b"x", kind="bogus").status_code == 422
    big = upload(client, auth, p["id"], "big.txt", b"x" * (1024 * 1024 + 1), kind="reference")
    assert big.status_code == 413


def test_upload_to_missing_or_deleted_project(client, auth):
    assert upload(client, auth, "tidak-ada").status_code == 404
    p = create(client, auth)
    client.delete(f"/api/projects/{p['id']}", headers=auth)
    assert upload(client, auth, p["id"]).status_code == 404


def test_list_download_and_delete_file(client, auth, settings):
    p = create(client, auth)
    f = upload(client, auth, p["id"], "spec.md", b"isi").json()
    assert [x["id"] for x in client.get(f"/api/projects/{p['id']}/files", headers=auth).json()] == [f["id"]]
    assert client.get(f"/api/projects/{p['id']}/files?kind=asset", headers=auth).json() == []

    d = client.get(f"/api/projects/{p['id']}/files/{f['id']}/download", headers=auth)
    assert d.status_code == 200 and d.content == b"isi"
    assert d.headers["x-content-type-options"] == "nosniff"
    assert d.headers["content-type"] == "application/octet-stream"
    assert "attachment" in d.headers["content-disposition"]

    assert client.delete(f"/api/projects/{p['id']}/files/{f['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/projects/{p['id']}/files", headers=auth).json() == []
    assert client.get(f"/api/projects/{p['id']}/files/{f['id']}/download", headers=auth).status_code == 404
    assert (settings.projects_dir / p["id"] / f["relative_path"]).is_file()


def test_file_of_other_project_is_not_reachable(client, auth):
    a, b = create(client, auth, "A"), create(client, auth, "B")
    f = upload(client, auth, a["id"]).json()
    assert client.get(f"/api/projects/{b['id']}/files/{f['id']}/download", headers=auth).status_code == 404
    assert client.delete(f"/api/projects/{b['id']}/files/{f['id']}", headers=auth).status_code == 404


def test_actions_are_audited(client, auth, settings):
    p = create(client, auth)
    upload(client, auth, p["id"])
    client.patch(f"/api/projects/{p['id']}", json={"name": "Baru"}, headers=auth)
    client.delete(f"/api/projects/{p['id']}", headers=auth)
    with client.app.state.session_factory() as s:
        actions = [a.action for a in s.scalars(select(AuditLog).order_by(AuditLog.created_at))]
    assert actions == ["project.create", "file.upload", "project.update", "project.delete"]
