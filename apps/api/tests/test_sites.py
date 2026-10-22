"""Situs yang dipasarkan Marketing/SEO (impor kode sumber, audit situs, kata kunci dari isi situs, serah terima)."""
import subprocess
from pathlib import Path

import pytest

from app.db.models import MarketingArtifact, Site
from app.marketing import sites
from app.marketing.import_site import main as cli_main
from app.projects.storage import ProjectStorage
from tests.fakes import FakeProvider
from tests.helpers import build_env, drain, get

PAGE_EN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Fatih Roihan | Freelance Website Developer for Business</title>
<meta name="description" content="Freelance website developer building landing pages, company profiles, and portfolio sites for small businesses with clear pricing.">
<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="canonical" href="https://contoh.site/"></head>
<body><h1>Websites that bring clients</h1><h2>Landing pages</h2><p>Company profiles and portfolio sites.</p><a href="/id/">ID</a></body></html>"""
PAGE_ID = PAGE_EN.replace('lang="en"', 'lang="id"').replace("https://contoh.site/", "https://contoh.site/id/").replace("Websites that bring clients", "Website yang mendatangkan klien")


def make_source(tmp_path: Path, git=True, hreflang=False) -> Path:
    src = tmp_path / "situs-asli"
    (src / "id").mkdir(parents=True)
    en = PAGE_EN.replace("</head>", '<link rel="alternate" hreflang="id" href="https://contoh.site/id/"></head>') if hreflang else PAGE_EN
    (src / "index.html").write_text(en, encoding="utf-8")
    (src / "id" / "index.html").write_text(PAGE_ID, encoding="utf-8")
    (src / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: https://contoh.site/sitemap.xml\n", encoding="utf-8")
    (src / "sitemap.xml").write_text("<urlset><url><loc>https://contoh.site/</loc></url><url><loc>https://contoh.site/id/</loc></url></urlset>", encoding="utf-8")
    (src / "assets").mkdir()
    (src / "assets" / "oops.html").write_text("<html>tidak ikut</html>", encoding="utf-8")
    if git:
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "awal"]):
            subprocess.run(["git", *cmd], cwd=src, check=True, capture_output=True)
    return src


def imported(env, src):
    with env.sf() as s:
        site = sites.import_site(s, env.storage, name="Portofolio Uji", url="https://contoh.site", source_path=str(src))
        s.commit()
        return site.id, site.project_id


def test_import_clones_git_history_and_leaves_original_untouched(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    src = make_source(tmp_path)
    before = sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if ".git" not in p.parts)
    sid, pid = imported(env, src)
    root = env.storage.project_dir(pid) / "workspace" / "source-code"
    assert (root / "index.html").exists() and (root / ".git").exists()
    assert subprocess.run(["git", "log", "--oneline"], cwd=root, capture_output=True, text=True).stdout.strip().endswith("awal")
    assert before == sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if ".git" not in p.parts)   # sumber tak berubah
    (root / "index.html").write_text("diubah", encoding="utf-8")                                                # salinan terpisah dari asli
    assert "Freelance" in (src / "index.html").read_text(encoding="utf-8")


def test_import_without_git_and_validations(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    sid, pid = imported(env, make_source(tmp_path, git=False))
    assert (env.storage.project_dir(pid) / "workspace" / "source-code" / ".git").exists()
    empty = tmp_path / "kosong"
    empty.mkdir()
    with env.sf() as s:
        for bad_path, url in ((tmp_path / "tidak-ada", "https://x.id"), (empty, "https://x.id"), (make_source(tmp_path / "b"), "ftp://x.id")):
            with pytest.raises(sites.SiteError):
                sites.import_site(s, env.storage, name="X", url=url, source_path=str(bad_path))


def test_collect_pages_skips_assets_symlinks_and_caps(migrated_db, tmp_path):
    src = make_source(tmp_path, git=False)
    try:
        (src / "tautan.html").symlink_to(tmp_path / "rahasia.html")
    except OSError:
        pass
    (tmp_path / "rahasia.html").write_text("<html>rahasia</html>", encoding="utf-8")
    b = sites.collect_pages(src, "https://contoh.site")
    assert [p["path"] for p in b["pages"]] == ["index.html", "id/index.html"]
    assert [p["url"] for p in b["pages"]] == ["https://contoh.site/", "https://contoh.site/id/"]
    assert b["robots_txt"].startswith("User-agent") and "<loc>" in b["sitemap_xml"]


def test_audit_site_finds_page_and_site_level_issues(tmp_path):
    src = make_source(tmp_path, git=False)
    r = sites.audit_site("https://contoh.site", sites.collect_pages(src, "https://contoh.site"))
    ids = {f["id"] for f in r["findings"]}
    assert "hreflang_missing" in ids and r["site_level"] and len(r["pages"]) == 2
    assert all(f["page"] for f in r["findings"])
    src2 = make_source(tmp_path / "b", git=False, hreflang=True)
    r2 = sites.audit_site("https://contoh.site", sites.collect_pages(src2, "https://contoh.site"))
    assert "hreflang_missing" not in {f["id"] for f in r2["findings"]}


def test_site_audit_task_runs_without_model_and_stores_artifact(migrated_db, tmp_path):
    from app.tasks import service
    env = build_env(migrated_db, tmp_path)
    sid, pid = imported(env, make_source(tmp_path, git=False))
    with env.sf() as s:
        t = service.create_task(s, project_id=pid, title="A", role="seo_specialist", action_type="seo_audit", params={"site_id": sid})
        service.queue_task(s, t)
        s.commit()
        tid = t.id
    drain(env)
    assert get(env, tid).status == "completed" and env.provider.calls == []
    with env.sf() as s:
        a = s.query(MarketingArtifact).one()
        assert a.kind == "audit" and a.data["site_id"] == sid and len(a.data["pages"]) == 2 and a.data["findings"]


def test_keywords_use_site_content_as_material(migrated_db, tmp_path):
    from app.tasks import service
    reply = '{"summary":"s","items":[{"keyword":"landing pages","intent":"commercial","priority":"high","rationale":"layanan utama","volume":null,"competition":"","evidence_quote":""}]}'
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=reply))
    sid, pid = imported(env, make_source(tmp_path, git=False))
    with env.sf() as s:
        t = service.create_task(s, project_id=pid, title="K", role="seo_specialist", action_type="keyword_research", params={"site_id": sid})
        service.queue_task(s, t)
        s.commit()
        tid = t.id
    drain(env)
    assert get(env, tid).status == "completed"
    prompt = env.provider.calls[0][1].prompt
    assert "Websites that bring clients" in prompt and "https://contoh.site/" in prompt


def test_unknown_site_fails_cleanly(migrated_db, tmp_path):
    from app.tasks import service
    env = build_env(migrated_db, tmp_path)
    from tests.helpers import make_project
    pid = make_project(env)
    with env.sf() as s:
        t = service.create_task(s, project_id=pid, title="A", role="seo_specialist", action_type="seo_audit", params={"site_id": "tidak-ada"})
        service.queue_task(s, t)
        s.commit()
        tid = t.id
    drain(env)
    assert get(env, tid).last_error_kind == "site_not_found"


def test_api_sites_flow_and_handoff_defaults_to_site_project(client, auth, settings, tmp_path):
    from app.db.session import create_db_engine, create_session_factory
    sf = create_session_factory(create_db_engine(settings.database_url))
    with sf() as s:
        site = sites.import_site(s, ProjectStorage(settings.projects_dir), name="Porto", url="https://contoh.site", source_path=str(make_source(tmp_path, git=False)))
        s.commit()
        sid, pid = site.id, site.project_id
    assert client.get("/api/marketing/seo/sites").status_code == 401
    lst = client.get("/api/marketing/seo/sites", headers=auth).json()
    assert [x["id"] for x in lst] == [sid] and lst[0]["last_audit"] is None
    d = client.get(f"/api/marketing/seo/sites/{sid}", headers=auth).json()
    assert [p["path"] for p in d["pages"]] == ["index.html", "id/index.html"] and d["has_robots"] and d["has_sitemap"]
    assert client.get("/api/marketing/seo/sites/tidak-ada", headers=auth).status_code == 404
    for path, body in (("audit", None), ("keywords", {"material": "m"}), ("brief", {})):
        r = client.post(f"/api/marketing/seo/sites/{sid}/tasks/{path}", json=body, headers=auth) if body is not None else client.post(f"/api/marketing/seo/sites/{sid}/tasks/{path}", headers=auth)
        assert r.status_code == 201
    assert client.post("/api/marketing/seo/sites/tidak-ada/tasks/audit", headers=auth).status_code == 404
    report = sites.audit_site("https://contoh.site", sites.collect_pages(Path(settings.projects_dir) / pid / "workspace" / "source-code", "https://contoh.site"))
    report["site_id"] = sid
    with sf() as s:
        a = MarketingArtifact(kind="audit", title="Audit situs", summary="s", data=report)
        s.add(a)
        s.commit()
        aid = a.id
    assert client.get(f"/api/marketing/seo/sites/{sid}", headers=auth).json()["last_audit"]["id"] == aid
    r = client.post(f"/api/marketing/seo/artifacts/{aid}/handoff", json={}, headers=auth)
    assert r.status_code == 201
    t = client.get(f"/api/tasks/{r.json()['task_id']}", headers=auth).json()
    assert t["project_id"] == pid and "[(situs)]" in t["description"]


def test_cli_import(settings, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.marketing.import_site.get_settings", lambda: settings)
    src = make_source(tmp_path, git=False)
    assert cli_main(["--name", "Porto", "--url", "https://contoh.site", "--path", str(src)]) == 0
    assert "Situs terdaftar" in capsys.readouterr().out
    assert cli_main(["--name", "X", "--url", "https://contoh.site", "--path", str(tmp_path / "tidak-ada")]) == 1
