"""Situs web yang dipasarkan tim Marketing/SEO (mis. portofolio CEO): impor kode sumber ke workspace proyek, kumpulkan halaman, audit.

Kode sumber DISALIN (klon Git lokal) ke `workspace/source-code` proyek; folder asli tidak pernah diubah. Perubahan hasil Engineering
tinggal di salinan itu dan dibawa kembali ke situs asli oleh CEO sendiri (git pull); tidak ada push atau deployment dari sini.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models import Project, Site
from app.marketing import seo
from app.projects.storage import ProjectStorage
from app.workspace import git as workspace_git

MAX_PAGES = 20
MAX_PAGE_BYTES = seo.MAX_HTML
SKIP_DIRS = {".git", "node_modules", "assets", ".vscode", "scripts", "vendor"}


class SiteError(ValueError):
    pass


def _valid_url(url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme not in {"http", "https"} or not u.netloc:
        raise SiteError("URL situs harus berawalan http:// atau https://")
    return f"{u.scheme}://{u.netloc}"


def import_site(session: Session, storage: ProjectStorage, *, name: str, url: str, source_path: str, language: str = "id") -> Site:
    """Salin situs ke proyek baru. Menolak folder tanpa HTML, dan tidak menyentuh folder sumber."""
    src = Path(source_path).resolve()
    if not src.is_dir():
        raise SiteError(f"Folder sumber tidak ditemukan: {src}")
    if not any(src.glob("*.html")) and not any(src.glob("*/index.html")):
        raise SiteError("Folder sumber tidak berisi halaman HTML")
    base = _valid_url(url)
    project = Project(name=f"Situs: {name}"[:120], description=f"Salinan kode sumber situs {base} untuk Marketing/SEO dan Engineering")
    session.add(project)
    session.flush()
    storage.create_layout(project.id)
    dest = storage.project_dir(project.id) / "workspace" / "source-code"
    if dest.exists() and any(dest.iterdir()):
        raise SiteError("Workspace tujuan sudah berisi berkas")
    if (src / ".git").exists():
        p = subprocess.run(["git", "-c", "core.hooksPath=/dev/null/none", "clone", "--no-hardlinks", "-q", str(src), str(dest)], capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            raise SiteError(f"Gagal menyalin repositori: {(p.stderr or p.stdout).strip()[:200]}")
    else:
        shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "node_modules"))
        workspace_git.ensure_repo(dest)
        workspace_git.commit_all(dest, "Impor awal situs")
    site = Site(name=name, url=base, project_id=project.id, language=language, source_origin=str(src))
    session.add(site)
    session.flush()
    return site


def site_root(storage: ProjectStorage, site: Site) -> Path:
    return storage.project_dir(site.project_id) / "workspace" / "source-code"


def page_url(base: str, rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel == "index.html":
        return base + "/"
    if rel.endswith("/index.html"):
        return f"{base}/{rel[: -len('index.html')]}"
    return f"{base}/{rel}"


def _read(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def collect_pages(root: Path, base_url: str) -> dict:
    """Halaman HTML (maks. 20, tanpa tautan simbolik) beserta robots.txt dan sitemap.xml dari kode sumber."""
    rootr = root.resolve()
    rels: list[str] = []
    for dirpath, dirnames, filenames in os.walk(rootr):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink()]
        depth = len(Path(dirpath).relative_to(rootr).parts)
        if depth > 2:
            dirnames[:] = []
            continue
        for f in filenames:
            if f.endswith(".html") and (depth == 0 or f == "index.html"):
                p = Path(dirpath) / f
                if p.is_symlink() or rootr not in p.resolve().parents:
                    continue
                rels.append(p.relative_to(rootr).as_posix())
    rels = sorted(rels, key=lambda r: (r.count("/"), r))[:MAX_PAGES]
    pages = [{"path": r, "url": page_url(base_url, r), "html": _read(rootr / r, MAX_PAGE_BYTES)} for r in rels]
    return {"pages": pages, "robots_txt": _read(rootr / "robots.txt", 20_000), "sitemap_xml": _read(rootr / "sitemap.xml", 100_000)}


def audit_site(base_url: str, bundle: dict) -> dict:
    """Audit setiap halaman + pemeriksaan tingkat situs (hreflang antarbahasa, robots menyebut sitemap, halaman yatim dari sitemap)."""
    reports, flat = [], []
    for pg in bundle["pages"]:
        r = seo.audit_html(pg["url"], pg["html"], bundle["robots_txt"], bundle["sitemap_xml"])
        r["path"] = pg["path"]
        reports.append(r)
        for f in r["findings"]:
            if f["id"] in {"robots_not_provided", "sitemap_not_provided"} and len(reports) > 1:
                continue  # catatan tingkat situs cukup sekali
            flat.append({**f, "page": pg["path"]})
    site_findings = []
    if len(bundle["pages"]) > 1 and not any(re.search(r"hreflang\s*=", p["html"], re.I) for p in bundle["pages"]):
        site_findings.append(seo._f("hreflang_missing", "warning", "Situs punya beberapa halaman/bahasa tetapi tidak ada tautan hreflang.", "Tambahkan <link rel=\"alternate\" hreflang> antar versi bahasa."))
    if bundle["robots_txt"].strip() and "sitemap:" not in bundle["robots_txt"].lower():
        site_findings.append(seo._f("robots_no_sitemap", "info", "robots.txt tidak menyebut lokasi sitemap.", "Tambahkan baris 'Sitemap: <url>/sitemap.xml'."))
    if not bundle["pages"]:
        site_findings.append(seo._f("no_pages", "critical", "Tidak ada halaman HTML ditemukan pada kode sumber.", "Periksa isi workspace."))
    flat += [{**f, "page": "(situs)"} for f in site_findings]
    counts = {s: sum(1 for f in flat if f["severity"] == s) for s in ("critical", "warning", "info")}
    return {"url": base_url, "site_level": True, "pages": reports, "findings": flat, "counts": counts,
            "page": {"count": len(reports)}, "not_checked": seo.NOT_CHECKED}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self.head: list[str] = []
        self._h = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        self._h = tag in {"h1", "h2", "h3"}

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self._skip = max(0, self._skip - 1)
        self._h = False

    def handle_data(self, data):
        t = re.sub(r"\s+", " ", data).strip()
        if t and not self._skip:
            self.parts.append(t)
            if self._h:
                self.head.append(t)


def site_summary(bundle: dict, limit: int = 3000) -> str:
    """Ringkasan teks situs (judul, deskripsi, judul bagian, cuplikan isi) sebagai bahan fakta untuk riset kata kunci dan brief."""
    out: list[str] = []
    for pg in bundle["pages"][:4]:
        p = seo._Page()
        p.feed(pg["html"])
        t = _Text()
        t.feed(pg["html"])
        out.append(f"[{pg['url']}] Judul: {re.sub(chr(10), ' ', p.title).strip()} | Deskripsi: {p.meta.get('description', '')}")
        out.append("Bagian: " + "; ".join(t.head[:12]))
        out.append("Isi: " + " ".join(t.parts)[:600])
    return "\n".join(out)[:limit]
