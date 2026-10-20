from alembic import context

from app.config import get_settings
from app.db import models  # noqa: F401  (mendaftarkan tabel ke metadata)
from app.db.base import Base
from app.db.session import create_db_engine

target_metadata = Base.metadata


def _url() -> str:
    # URL dari -x url=... (dipakai tes), jika tidak ada pakai konfigurasi aplikasi.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(_url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
