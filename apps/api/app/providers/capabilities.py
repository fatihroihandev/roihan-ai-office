"""Sinkronisasi Model Capability Registry (Bagian 8.4)."""
import json
from pathlib import Path

from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import ModelCapability
from app.providers.registry import ProviderEntry


def latest_benchmark(data_dir: Path, model_id: str) -> dict | None:
    """Ringkasan benchmark terbaru untuk model (dihasilkan scripts/benchmark_ollama.py), jika ada."""
    files = sorted((data_dir / "benchmarks").glob(f"{model_id.replace(':', '_')}_*.json"))
    if not files:
        return None
    try:
        r = json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rate = lambda key: (r.get(key) or {}).get("rate")
    return {
        "json_valid_rate": rate("json"), "codegen_pass_rate": rate("codegen"), "bugfix_pass_rate": rate("bugfix"),
        "avg_tok_per_s": (r.get("speed") or {}).get("avg_tok_per_s"),
        "source": files[-1].name, "finished_at": r.get("finished_at"),
    }


async def sync_provider_models(session_factory, entry: ProviderEntry, data_dir: Path) -> list[ModelCapability]:
    """Ambil model dari provider, perbarui registri, dan tandai model yang hilang sebagai tidak tersedia."""
    infos = await entry.provider.list_models()
    detailed = []
    for info in infos:
        try:
            detailed.append(await entry.provider.get_capabilities(info.model_id))
        except Exception:
            detailed.append(info)  # pakai data dari daftar jika detail gagal diambil

    with session_factory() as s:
        existing = {m.model_id: m for m in s.scalars(select(ModelCapability).where(ModelCapability.provider == entry.name))}
        seen = set()
        for info in detailed:
            seen.add(info.model_id)
            row = existing.get(info.model_id) or ModelCapability(provider=entry.name, model_id=info.model_id)
            row.available, row.is_paid = True, entry.is_paid
            row.context_limit, row.supports_tools, row.supports_vision = info.context_limit, info.supports_tools, info.supports_vision
            row.details, row.refreshed_at = info.details or None, utcnow()
            bench = latest_benchmark(data_dir, info.model_id)
            row.benchmark = bench
            row.validation_status = "benchmarked" if bench else "unvalidated"
            s.add(row)
        for model_id, row in existing.items():
            if model_id not in seen:
                row.available, row.refreshed_at = False, utcnow()
        s.commit()
        return list(s.scalars(select(ModelCapability).where(ModelCapability.provider == entry.name)
                              .order_by(ModelCapability.model_id)))
