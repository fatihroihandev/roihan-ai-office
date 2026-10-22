"""Executor SEO Specialist dan Marketing Analytics (Phase 14). Keduanya hanya MENGHASILKAN artefak untuk ditinjau:
tidak mengubah kode produksi, tidak memublikasikan, dan tidak mengirim apa pun (publikasi tetap lewat Content & Promotion + approval).
"""
from pydantic import BaseModel, Field, ValidationError

from app.db.models import MarketingArtifact
from app.marketing import access, seo
from app.marketing.agents import _EMAIL_IN_TEXT, MAX_MATERIAL, _brief, _params
from app.marketing.privacy import PolicyError, assert_clean
from app.products.claims import check_claims
from app.tasks.executors import ExecutionContext, ExecutorError, ExecutorOutcome, extract_json

KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}, "items": {"type": "array", "maxItems": 25, "items": {
        "type": "object",
        "properties": {"keyword": {"type": "string"}, "intent": {"type": "string", "enum": sorted(seo.INTENTS)},
                       "priority": {"type": "string", "enum": ["high", "medium", "low"]}, "rationale": {"type": "string"},
                       "volume": {"type": ["integer", "null"]}, "competition": {"type": "string"}, "evidence_quote": {"type": "string"}},
        "required": ["keyword", "intent", "priority", "rationale", "volume", "competition", "evidence_quote"]}}},
    "required": ["summary", "items"],
}
BRIEF_SCHEMA = {
    "type": "object",
    "properties": {"title_options": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
                   "search_intent": {"type": "string"},
                   "outline": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {"heading": {"type": "string"}, "points": {"type": "array", "items": {"type": "string"}}},
                                                                            "required": ["heading", "points"]}},
                   "faq": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                   "internal_links": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                   "avoid_claims": {"type": "array", "maxItems": 8, "items": {"type": "string"}}},
    "required": ["title_options", "search_intent", "outline", "faq", "internal_links", "avoid_claims"],
}


class KeywordsOut(BaseModel):
    summary: str = Field(default="", max_length=2000)
    items: list[dict] = Field(default_factory=list, max_length=25)


class BriefOut(BaseModel):
    title_options: list[str] = Field(default_factory=list, max_length=5)
    search_intent: str = ""
    outline: list[dict] = Field(default_factory=list, max_length=12)
    faq: list[str] = Field(default_factory=list, max_length=8)
    internal_links: list[str] = Field(default_factory=list, max_length=8)
    avoid_claims: list[str] = Field(default_factory=list, max_length=8)


def _store(ctx: ExecutionContext, kind: str, title: str, summary: str, data: dict, verified: int = 0, unverified: int = 0) -> str:
    with ctx.session_factory() as s:
        row = MarketingArtifact(task_id=ctx.task.id, kind=kind, title=title[:200], summary=summary, data=data,
                                verified_count=verified, unverified_count=unverified, created_by=ctx.task.role)
        s.add(row)
        s.commit()
        return row.id


async def _ask(ctx: ExecutionContext, system: str, prompt: str, schema: dict, model_cls, max_tokens: int):
    parsed, error = None, None
    for _ in range(2):
        res = await ctx.generate(system, prompt + (f"\n\nJawaban sebelumnya ditolak: {error}" if error else ""), max_tokens=max_tokens, json_schema=schema)
        try:
            if res.truncated:
                raise ValueError("jawaban terpotong")
            parsed = model_cls.model_validate(extract_json(res.text))
            break
        except (ValidationError, ValueError) as e:
            error = str(e)[:300]
    if parsed is None:
        raise ExecutorError("invalid_seo_output", f"Keluaran tidak valid: {error}")
    return parsed


class SeoSpecialistExecutor:
    """seo_audit (deterministik, tanpa model), keyword_research, content_brief (model hanya mengusulkan; diperiksa terhadap materi)."""

    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        access.require("seo_specialist", "seo.write")
        action = ctx.task.action_type
        p = _params(ctx)
        if action == "seo_audit":
            return self._audit(ctx, p)
        if action not in {"keyword_research", "content_brief"}:
            raise ExecutorError("unsupported_action", "SEO Specialist hanya mengerjakan seo_audit, keyword_research, content_brief", retryable=False)
        topic, material = (p.get("topic") or ctx.task.title).strip(), (p.get("material") or "").strip()
        if len(material) > MAX_MATERIAL:
            raise ExecutorError("invalid_material", f"Materi maks. {MAX_MATERIAL} karakter", retryable=False)
        if action == "keyword_research" and not material:
            raise ExecutorError("invalid_material", "Materi riset kata kunci wajib diisi (data/pengetahuan yang Anda miliki)", retryable=False)
        if _EMAIL_IN_TEXT.search(material):
            raise ExecutorError("pii_in_material", "Materi tidak boleh memuat alamat email/data kontak pribadi", retryable=False)
        try:
            assert_clean(topic=topic, material=material)
        except PolicyError as e:
            raise ExecutorError("sensitive_data", e.message, retryable=False) from e
        with ctx.session_factory() as s:
            brief = _brief(s, p.get("product_id"), p.get("version_id"))
        brief_text = ""
        if brief is not None:
            brief_text = "\n".join([brief["product"]["name"], brief["product"].get("description") or ""] + [c["text"] for c in brief["claims"]])
        base = [f"TOPIK: {topic}", f"MATERI SUMBER (satu-satunya bahan fakta dan angka):\n{material or '(tidak ada)'}",
                f"INFORMASI PRODUK RESMI:\n{brief_text}" if brief_text else "INFORMASI PRODUK: (tidak ada)"]
        system = ("Kamu adalah SEO Specialist untuk Roihan Software House. Kamu tidak punya akses internet dan tidak boleh mengarang volume pencarian, "
                  "tingkat persaingan, atau klaim produk. Jangan menjanjikan atau menjamin peringkat atau pendapatan.")
        if action == "keyword_research":
            prompt = "\n\n".join(base + ["Usulkan kata kunci relevan untuk layanan software development, kelompokkan menurut niat pencarian. Isi volume dan "
                                         "competition HANYA bila angkanya tertulis di materi (salin kutipan PERSIS ke evidence_quote yang memuat kata kunci itu); "
                                         "jika tidak, volume=null, competition kosong, evidence_quote kosong. Balas HANYA JSON."])
            out = await _ask(ctx, system, prompt, KEYWORD_SCHEMA, KeywordsOut, 1800)
            items = seo.ground_keywords(out.items, material)
            if not items:
                raise ExecutorError("no_keywords", "Tidak ada kata kunci valid pada keluaran model")
            with_data = sum(1 for i in items if i["data_available"])
            flagged = sum(1 for i in items if i["flagged_claims"])
            text = f"Riset kata kunci '{topic}': {len(items)} kata kunci, {with_data} dengan data volume/persaingan dari materi, {len(items) - with_data} tanpa data (tidak diisi)."
            aid = _store(ctx, "keywords", f"Kata kunci: {topic}", out.summary, {"items": items, "flagged_items": flagged}, with_data, len(items) - with_data)
            return ExecutorOutcome(output=text, verified=True, verification={"method": "keyword_data_grounding", "passed": True, "with_data": with_data, "without_data": len(items) - with_data},
                                   result={"output": text, "artifact_id": aid})
        prompt = "\n\n".join(base + [f"Susun content brief untuk topik/kata kunci '{p.get('keyword') or topic}': opsi judul, niat pencarian, kerangka bagian, FAQ, saran tautan internal, "
                                     "dan klaim yang harus dihindari. Hanya sebut fitur produk yang ada pada INFORMASI PRODUK RESMI. Balas HANYA JSON."])
        out = await _ask(ctx, system, prompt, BRIEF_SCHEMA, BriefOut, 1800)
        all_text = " ".join(out.title_options + [out.search_intent] + [str(o.get("heading", "")) + " " + " ".join(map(str, o.get("points", []))) for o in out.outline] + out.faq)
        flagged = seo.lint_seo_claims(all_text)
        claims = check_claims(all_text, brief) if brief is not None else None
        if flagged or (claims is not None and not claims["ok"]):
            raise ExecutorError("claims_blocked", f"Brief memuat klaim terlarang: jaminan peringkat={flagged}; klaim produk={[f.get('message') for f in (claims or {}).get('findings', [])][:3]}", retryable=False)
        text = f"Content brief '{topic}': {len(out.outline)} bagian, {len(out.faq)} FAQ."
        aid = _store(ctx, "brief", f"Brief: {topic}", out.search_intent, {**out.model_dump(), "claims_check": claims}, 1, 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "claim_lint", "passed": True}, result={"output": text, "artifact_id": aid})

    def _audit(self, ctx: ExecutionContext, p: dict) -> ExecutorOutcome:
        html = (p.get("html") or "")
        if not html.strip() or len(html) > seo.MAX_HTML:
            raise ExecutorError("invalid_html", f"HTML halaman wajib diisi (maks. {seo.MAX_HTML} karakter)", retryable=False)
        report = seo.audit_html(p.get("url") or "", html, p.get("robots_txt") or "", p.get("sitemap_xml") or "")
        c = report["counts"]
        text = f"Audit SEO {report['url'] or '(tanpa URL)'}: {c['critical']} kritis, {c['warning']} peringatan, {c['info']} info. Tidak diperiksa: {', '.join(report['not_checked'])}."
        aid = _store(ctx, "audit", f"Audit: {report['url'] or 'halaman'}", text, report, len(report["findings"]), 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "deterministic_html_audit", "passed": True, **c}, result={"output": text, "artifact_id": aid})


class MarketingAnalyticsExecutor:
    """Laporan KPI deterministik dari data yang tercatat (tanpa model): nilai tidak diketahui tetap None, ROI hanya bila datanya lengkap."""

    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        access.require("marketing_analytics", "analytics.read")
        if ctx.task.action_type != "marketing_analysis":
            raise ExecutorError("unsupported_action", "Marketing Analytics hanya mengerjakan marketing_analysis", retryable=False)
        with ctx.session_factory() as s:
            k = seo.kpis(s)
        observations = []
        if k["organic"]["impressions"] is None:
            observations.append("Data impresi pencarian belum dicatat: kinerja organik belum dapat dinilai.")
        elif k["organic"]["ctr"] is not None:
            observations.append(f"CTR organik tercatat {k['organic']['ctr']:.2%} dari {int(k['organic']['impressions'])} impresi (data periode yang dicatat).")
        if k["funnel"]["lead_to_meeting_rate"] is None:
            observations.append("Rasio lead ke pertemuan belum diketahui (belum ada lead).")
        if k["money"]["roi"] is None:
            observations.append("ROI belum dihitung karena biaya dan pendapatan kampanye belum lengkap.")
        observations.append("Pengamatan ini deskriptif; bukan bukti sebab-akibat dan bukan jaminan hasil.")
        text = f"Laporan analitik pemasaran: {k['leads']['total']} lead, {sum(1 for v in _flat(k) if v is None)} indikator belum diketahui."
        aid = _store(ctx, "analysis", "Laporan analitik pemasaran", text, {"kpis": k, "observations": observations}, 1, 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "deterministic_kpi_report", "passed": True}, result={"output": text, "artifact_id": aid})


def _flat(d):
    for v in d.values():
        if isinstance(v, dict):
            yield from _flat(v)
        elif not isinstance(v, (list, str)):
            yield v
