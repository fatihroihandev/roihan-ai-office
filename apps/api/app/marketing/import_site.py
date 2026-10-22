"""CLI: python -m app.marketing.import_site --name "Portofolio" --url https://contoh.site --path C:\\folder\\situs

Menyalin kode sumber situs ke proyek baru di platform (folder asli tidak diubah) dan mendaftarkannya sebagai situs pemasaran.
"""
import argparse
import sys

from app.config import get_settings
from app.db.session import create_db_engine, create_session_factory
from app.marketing import sites
from app.projects.storage import ProjectStorage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.marketing.import_site")
    ap.add_argument("--name", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--language", default="id")
    a = ap.parse_args(argv)
    s = get_settings()
    sf = create_session_factory(create_db_engine(s.database_url))
    try:
        with sf() as session:
            site = sites.import_site(session, ProjectStorage(s.projects_dir), name=a.name, url=a.url, source_path=a.path, language=a.language)
            session.commit()
            print(f"Situs terdaftar: id={site.id} proyek={site.project_id} url={site.url}")
    except sites.SiteError as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
