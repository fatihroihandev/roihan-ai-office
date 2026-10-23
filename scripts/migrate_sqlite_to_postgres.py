"""Copy all application rows from SQLite to an already-migrated, empty PostgreSQL database.

Run from the repository root with the API virtualenv:
    apps/api/.venv/Scripts/python scripts/migrate_sqlite_to_postgres.py \
      sqlite:///data/database/roihan.db postgresql+psycopg://user:password@localhost:5432/roihan
"""
from __future__ import annotations

import sys

from sqlalchemy import MetaData, create_engine, func, insert, select, text
from sqlalchemy.engine import make_url

sys.path.insert(0, "apps/api")
from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402

BATCH_SIZE = 1000


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Pemakaian: migrate_sqlite_to_postgres.py <sqlite-url> <postgres-url>")
    source_url, target_url = map(make_url, sys.argv[1:])
    if source_url.get_backend_name() != "sqlite" or target_url.get_backend_name() != "postgresql":
        raise SystemExit("Sumber harus SQLite dan tujuan harus PostgreSQL.")

    source = create_engine(source_url)
    target = create_engine(target_url)
    metadata: MetaData = Base.metadata
    tables = list(metadata.sorted_tables)
    try:
        with source.connect() as src, target.begin() as dst:
            # Require a migrated schema and an empty application database, avoiding accidental merges.
            target_tables = set(dst.dialect.get_table_names(dst))
            for table in tables:
                if table.name not in target_tables:
                    raise RuntimeError(f"Tabel tujuan tidak ada: {table.name}; jalankan alembic upgrade head dahulu.")
                if dst.scalar(select(func.count()).select_from(table)):
                    raise RuntimeError(f"Tabel tujuan tidak kosong: {table.name}; migrasi dibatalkan.")

            copied: dict[str, int] = {}
            for table in tables:
                offset = 0
                count = 0
                while True:
                    rows = src.execute(select(table).limit(BATCH_SIZE).offset(offset)).mappings().all()
                    if not rows:
                        break
                    dst.execute(insert(table), [dict(row) for row in rows])
                    count += len(rows)
                    offset += len(rows)
                copied[table.name] = count

            # Explicitly inserted integer identity values must advance PostgreSQL sequences.
            for table in tables:
                for column in table.columns:
                    if column.primary_key and column.autoincrement is True and column.type.python_type is int:
                        sequence = dst.scalar(text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                                              {"table_name": table.name, "column_name": column.name})
                        if sequence:
                            preparer = dst.dialect.identifier_preparer
                            table_sql = preparer.quote(table.name)
                            column_sql = preparer.quote(column.name)
                            dst.execute(text(f"SELECT setval(:sequence, COALESCE((SELECT MAX({column_sql}) FROM {table_sql}), 1), "
                                             f"(SELECT COUNT(*) > 0 FROM {table_sql}))"), {"sequence": sequence})
        print("Selesai menyalin baris:")
        for name, count in copied.items():
            print(f"  {name}: {count}")
    finally:
        source.dispose()
        target.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
