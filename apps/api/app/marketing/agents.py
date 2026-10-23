"""Agent Marketing: Market Research, Lead Generation (intake), dan Sales (draf outreach).

Prinsip: model hanya MENGUSULKAN; setiap fakta diperiksa terhadap materi yang diberikan sebelum disimpan.
Tidak ada pengiriman apa pun: draf hanya disimpan untuk ditinjau CEO (Phase 9 menambah konektor + approval).
"""
import re

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.db.models import Company, ContentAsset, Lead, MarketResearch, OutreachRecord, Product, ProductVersion, Project, Task
from app.marketing import external, service
from app.marketing.external import OPT_OUT_FOOTER
from app.marketing.access import AccessDenied
from app.marketing.policy import Policy, validate_source_type, validate_url
from app.marketing.privacy import PolicyError, assert_clean, normalize_domain
from app.products import service as products
from app.products.claims import check_claims
from app.tasks import service as task_service
from app.tasks.executors import ExecutionContext, ExecutorError, ExecutorOutcome, extract_json

MARKETING_PROJECT_NAME = "Marketing"
MAX_MATERIAL = 8000
MAX_CANDIDATES = 20
_EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


def ensure_marketing_project(session, storage) -> str:
    """Task Marketing memerlukan project; gunakan satu proyek internal 'Marketing' (dibuat sekali)."""
    p = session.scalar(select(Project).where(Project.name == MARKETING_PROJECT_NAME, Project.deleted_at.is_(None)))
    if p is None:
        p = Project(name=MARKETING_PROJECT_NAME, description="Proyek internal untuk pekerjaan Marketing dan Sales")
        session.add(p)
        session.flush()
        storage.create_layout(p.id)
    return p.id


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def in_material(fragment: str | None, material: str) -> bool:
    """Apakah kutipan muncul apa adanya (spasi dinormalisasi) di materi sumber."""
    f = _norm(fragment or "")
    return len(f) >= 3 and f in _norm(material)


def _params(ctx: ExecutionContext) -> dict:
    return dict(ctx.task.params or {})


def _policy(ctx: ExecutionContext) -> Policy:
    return Policy.from_settings(ctx.settings)


def _brief(session, product_id: str | None, version_id: str | None) -> dict | None:
    if not product_id:
        return None
    product = session.get(Product, product_id)
    if product is None:
        raise ExecutorError("product_not_found", "Produk tidak ditemukan", retryable=False)
    version = session.get(ProductVersion, version_id) if version_id else products.current_version(session, product)
    if version is None or version.product_id != product.id:
        raise ExecutorError("version_not_found", "Versi produk tidak ditemukan", retryable=False)
    return products.marketing_brief(session, product, version)


# ------------------------------------------------------------------ Market Research

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {"type": "array", "maxItems": 10, "items": {
            "type": "object",
            "properties": {"statement": {"type": "string"},
                           "basis": {"type": "string", "enum": ["provided_material", "product_catalog", "assumption"]},
                           "evidence_quote": {"type": "string"}},
            "required": ["statement", "basis", "evidence_quote"]}},
    },
    "required": ["summary", "items"],
}


class ResearchItem(BaseModel):
    statement: str = Field(min_length=3, max_length=600)
    basis: str
    evidence_quote: str = Field(default="", max_length=600)


class ResearchOut(BaseModel):
    summary: str = Field(default="", max_length=3000)
    items: list[ResearchItem] = Field(default_factory=list, max_length=10)


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").casefold()) if len(w) >= 4}


def _supports(statement: str, quote: str, threshold: float = 0.5) -> bool:
    words = _content_words(statement)
    return bool(words) and len(words & _content_words(quote)) / len(words) >= threshold


def ground_research(items: list[ResearchItem], material: str, brief_text: str) -> list[dict]:
    """Temuan hanya `verified` jika kutipan buktinya benar-benar ada pada sumbernya; selain itu diberi label belum terverifikasi."""
    out = []
    for it in items:
        source = {"provided_material": material, "product_catalog": brief_text}.get(it.basis)
        # kutipan harus ada di sumber DAN benar-benar berkaitan dengan pernyataan (heuristik: kata isi pernyataan ada di kutipan)
        grounded = source is not None and in_material(it.evidence_quote, source) and _supports(it.statement, it.evidence_quote)
        out.append({"statement": it.statement.strip(), "basis": it.basis if grounded else "assumption",
                    "claimed_basis": it.basis, "evidence_quote": it.evidence_quote.strip() if grounded else "",
                    "verified": grounded})
    return out


class MarketResearchExecutor:
    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if ctx.task.action_type != "market_research":
            raise ExecutorError("unsupported_action", "Market Research hanya mengerjakan task market_research", retryable=False)
        p = _params(ctx)
        topic, material = (p.get("topic") or ctx.task.title).strip(), (p.get("material") or "").strip()
        if not material or len(material) > MAX_MATERIAL:
            raise ExecutorError("invalid_material", f"Materi riset wajib diisi (maks. {MAX_MATERIAL} karakter)", retryable=False)
        if _EMAIL_IN_TEXT.search(material):
            raise ExecutorError("pii_in_material", "Materi riset tidak boleh memuat alamat email/data kontak pribadi", retryable=False)
        try:
            assert_clean(topic=topic, material=material)
        except PolicyError as e:
            raise ExecutorError("sensitive_data", e.message, retryable=False) from e
        with ctx.session_factory() as s:
            brief = _brief(s, p.get("product_id"), p.get("version_id"))
        brief_text = ""
        if brief is not None:
            brief_text = "\n".join([brief["product"]["name"], brief["product"].get("description") or "",
                                    brief["product"].get("target_customers") or ""] + [c["text"] for c in brief["claims"]])
        prompt = "\n\n".join([
            f"TOPIK RISET: {topic}",
            f"MATERI SUMBER (satu-satunya bahan fakta):\n{material}",
            f"INFORMASI PRODUK RESMI:\n{brief_text}" if brief_text else "INFORMASI PRODUK: (tidak ada)",
            "Susun temuan riset. Untuk setiap temuan: basis = provided_material jika kalimat itu didukung materi (salin kutipan PERSIS ke "
            "evidence_quote), product_catalog jika didukung informasi produk, assumption jika hanya dugaan (evidence_quote kosong). "
            "Jangan mengarang angka, nama perusahaan, atau kutipan. Balas HANYA JSON.",
        ])
        system = ("Kamu adalah Market Research Agent. Kamu tidak punya akses internet dan tidak boleh mengarang data pasar. "
                  "Pisahkan dengan jelas fakta dari materi dan asumsi.")
        parsed, error = None, None
        for _ in range(2):
            res = await ctx.generate(system, prompt + (f"\n\nJawaban sebelumnya ditolak: {error}" if error else ""), max_tokens=1500,
                                     json_schema=RESEARCH_SCHEMA)
            try:
                if res.truncated:
                    raise ValueError("jawaban terpotong")
                parsed = ResearchOut.model_validate(extract_json(res.text))
                break
            except (ValidationError, ValueError) as e:
                error = str(e)[:300]
        if parsed is None:
            raise ExecutorError("invalid_research_output", f"Keluaran riset tidak valid: {error}")
        items = ground_research(parsed.items, material, brief_text)
        verified = sum(1 for i in items if i["verified"])
        with ctx.session_factory() as s:
            row = MarketResearch(task_id=ctx.task.id, product_id=p.get("product_id"), topic=topic[:200], summary=parsed.summary,
                                 items=items, sources=[{"type": "provided_material", "chars": len(material)}],
                                 verified_count=verified, unverified_count=len(items) - verified)
            s.add(row)
            s.commit()
            rid = row.id
        text = f"Riset '{topic}': {verified} temuan terverifikasi dari materi, {len(items) - verified} asumsi/belum terverifikasi."
        return ExecutorOutcome(output=text, verified=True,
                               verification={"method": "evidence_quote_grounding", "passed": True, "verified": verified,
                                             "unverified": len(items) - verified},
                               result={"output": text, "research_id": rid})


# ------------------------------------------------------------------ Lead Generation (intake dari teks yang diberikan)

CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {"candidates": {"type": "array", "maxItems": MAX_CANDIDATES, "items": {
        "type": "object",
        "properties": {k: {"type": "string"} for k in ("company_name", "industry", "city", "website", "size_band", "contact_name",
                                                       "contact_title", "contact_email", "contact_phone", "evidence_quote")},
        "required": ["company_name", "industry", "city", "website", "size_band", "contact_name", "contact_title", "contact_email",
                     "contact_phone", "evidence_quote"]}}},
    "required": ["candidates"],
}


class Candidate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    industry: str = ""
    city: str = ""
    website: str = ""
    size_band: str = ""
    contact_name: str = ""
    contact_title: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    evidence_quote: str = ""


class CandidatesOut(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list, max_length=MAX_CANDIDATES)


def ground_candidate(c: Candidate, material: str) -> tuple[str | None, Candidate, list[str]]:
    """Periksa kandidat terhadap materi sumber. Nama perusahaan dan kutipan bukti WAJIB ada di materi (jika tidak: ditolak).
    Field kontak/website yang tidak ditemukan di materi DIBUANG (bukan disimpan) dan dicatat; sisanya tetap dipakai."""
    if not in_material(c.company_name, material):
        return "nama perusahaan tidak ditemukan pada materi", c, []
    if not in_material(c.evidence_quote, material):
        return "kutipan bukti tidak ditemukan pada materi", c, []
    clean, dropped = c.model_copy(), []
    if clean.contact_email and clean.contact_email.strip().casefold() not in material.casefold():
        clean.contact_email = ""
        dropped.append("contact_email")
    if clean.contact_phone:
        digits, mat_digits = re.sub(r"\D", "", clean.contact_phone), re.sub(r"\D", "", material)
        if len(digits) < 6 or digits.lstrip("0")[-8:] not in mat_digits:
            clean.contact_phone = ""
            dropped.append("contact_phone")
    for field in ("contact_name", "contact_title", "website"):
        v = getattr(clean, field)
        if v and not in_material(v, material):
            setattr(clean, field, "")
            dropped.append(field)
    return None, clean, dropped


def context_emails(c: Candidate, material: str) -> set[str]:
    """Email yang tertulis pada baris materi yang menyebut perusahaan ini. Dipakai memeriksa daftar jangan-hubungi walaupun
    model tidak mengekstrak kontaknya, supaya perusahaan/kontak yang menolak tidak lolos hanya karena field kontak dikosongkan."""
    name = _norm(c.company_name)
    found: set[str] = set()
    for line in material.splitlines():
        if name and name in _norm(line):
            found |= {e.lower() for e in _EMAIL_IN_TEXT.findall(line)}
    return found


class LeadIntakeExecutor:
    idempotent = False      # membuat data; jangan diulang otomatis setelah terinterupsi

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if ctx.task.action_type != "lead_intake":
            raise ExecutorError("unsupported_action", "Lead Generation hanya mengerjakan task lead_intake", retryable=False)
        p = _params(ctx)
        material, source = (p.get("raw_text") or "").strip(), dict(p.get("source") or {})
        policy = _policy(ctx)
        if not material or len(material) > MAX_MATERIAL:
            raise ExecutorError("invalid_material", f"Teks sumber wajib diisi (maks. {MAX_MATERIAL} karakter)", retryable=False)
        try:                                   # kebijakan sumber diperiksa SEBELUM memanggil model
            rule = validate_source_type(policy, source.get("source_type", ""))
            validate_url(source.get("url"), rule["needs_url"])
        except PolicyError as e:
            raise ExecutorError(e.code, e.message, retryable=False) from e
        prompt = (f"TEKS SUMBER:\n{material}\n\nEkstrak perusahaan (dan kontak bisnis bila ada) yang DISEBUTKAN di teks. "
                  "Salin nilai persis seperti tertulis; kosongkan jika tidak ada. evidence_quote = kalimat persis dari teks yang menyebut "
                  "perusahaan itu. size_band salah satu: micro, small, medium, large, unknown. Jangan menambah data dari pengetahuanmu. Balas HANYA JSON.")
        system = "Kamu adalah Lead Generation Agent. Kamu hanya mengekstrak data yang tertulis di teks yang diberikan, tidak pernah mengarang."
        parsed, error = None, None
        for _ in range(2):
            res = await ctx.generate(system, prompt + (f"\n\nJawaban sebelumnya ditolak: {error}" if error else ""), max_tokens=1800,
                                     json_schema=CANDIDATE_SCHEMA)
            try:
                if res.truncated:
                    raise ValueError("jawaban terpotong")
                parsed = CandidatesOut.model_validate(extract_json(res.text))
                break
            except (ValidationError, ValueError) as e:
                error = str(e)[:300]
        if parsed is None:
            raise ExecutorError("invalid_intake_output", f"Keluaran ekstraksi tidak valid: {error}")

        created, draft_task_ids, skipped, source_id, dropped_fields = [], [], [], None, {}
        with ctx.session_factory() as s:
            for c in parsed.candidates:
                label = c.company_name[:80]
                why, c, dropped = ground_candidate(c, material)
                if why:
                    skipped.append({"company": label, "code": "not_grounded", "reason": why})
                    continue
                if any(service.is_suppressed(s, email=e) for e in context_emails(c, material)):
                    skipped.append({"company": label, "code": "suppressed", "reason": "kontak pada teks sumber ada di daftar jangan-hubungi"})
                    continue
                if c.website:                      # website hanya pelengkap: yang tidak valid dibuang, bukan alasan menolak prospek
                    try:
                        normalize_domain(validate_url(c.website, False))
                    except PolicyError:
                        c.website = ""
                        dropped.append("website")
                size = c.size_band if c.size_band in {"micro", "small", "medium", "large", "unknown"} else "unknown"
                try:
                    with s.begin_nested():
                        lead = service.create_lead(
                            s, policy, actor="lead_generation",
                            company={"name": c.company_name, "industry": c.industry or None, "city": c.city or None,
                                     "website": c.website or None, "size_band": size},
                            contact={"name": c.contact_name, "title": c.contact_title, "email": c.contact_email, "phone": c.contact_phone},
                            source=source_id or {"source_type": source["source_type"], "url": source.get("url"), "title": source.get("title"),
                                                 "method": "agent_extraction"},
                            product_id=p.get("product_id"))
                        source_id = lead.source_id
                    created.append(lead.id)
                    if dropped:
                        dropped_fields[lead.id] = dropped
                    if p.get("product_id"):
                        draft_task = task_service.create_task(
                            s, project_id=ctx.task.project_id, parent_task_id=ctx.task.id,
                            title=f"Siapkan promosi untuk {c.company_name[:80]}",
                            role="sales_client_relations", action_type="draft_outreach", max_retries=1,
                            created_by="lead_generation",
                            params={"lead_id": lead.id, "product_id": p["product_id"], "channel": "email", "auto_prospecting": True},
                        )
                        task_service.queue_task(s, draft_task, actor="ceo")
                        draft_task_ids.append(draft_task.id)
                except (PolicyError, service.MarketingError, AccessDenied) as e:
                    skipped.append({"company": label, "code": getattr(e, "code", "denied"), "reason": str(e)[:200]})
            s.commit()
        text = f"{len(created)} prospek dibuat, {len(skipped)} dilewati"
        return ExecutorOutcome(output=text, verified=True,
                               verification={"method": "source_text_grounding", "passed": True, "created": len(created), "skipped": len(skipped)},
                               result={"output": text, "created_lead_ids": created, "draft_task_ids": draft_task_ids,
                                       "skipped": skipped, "ungrounded_fields_dropped": dropped_fields})


# ------------------------------------------------------------------ Sales & Client Relations (draf outreach)

OUTREACH_SCHEMA = {"type": "object", "properties": {"subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["subject", "body"]}


class OutreachOut(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=3000)


class SalesOutreachExecutor:
    idempotent = False

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if ctx.task.action_type == "external_outreach":
            return _enqueue_outbound(ctx, "outreach", "sales_client_relations")
        if ctx.task.action_type != "draft_outreach":
            raise ExecutorError("unsupported_action", "Sales hanya mengerjakan task draft_outreach atau external_outreach", retryable=False)
        p = _params(ctx)
        actor = "sales_client_relations"
        with ctx.session_factory() as s:
            lead = s.get(Lead, p.get("lead_id") or "")
            if lead is None:
                raise ExecutorError("lead_not_found", "Prospek tidak ditemukan", retryable=False)
            try:
                service._lead_open(lead)
                parent = s.get(Task, ctx.task.parent_task_id) if ctx.task.parent_task_id else None
                auto_prospecting = bool(
                    p.get("auto_prospecting") is True
                    and ctx.task.created_by == "lead_generation"
                    and parent is not None
                    and parent.role == "lead_generation"
                    and parent.action_type == "lead_intake"
                    and p.get("product_id") == lead.product_id
                )
                if not auto_prospecting and (lead.forwarded_at is None or lead.owner != actor):
                    raise service.MarketingError("not_forwarded", "Prospek belum diteruskan ke Sales")
                if lead.contact_email and service.is_suppressed(s, email=lead.contact_email):
                    raise service.MarketingError("suppressed", "Kontak ada di daftar jangan-hubungi")
                pii = service.pii_for_actor(s, lead, actor)
            except (service.MarketingError, AccessDenied) as e:
                raise ExecutorError(getattr(e, "code", "denied"), str(e), retryable=False) from e
            brief = _brief(s, p.get("product_id") or lead.product_id, p.get("version_id"))
            if brief is None:
                raise ExecutorError("product_required", "Draf outreach memerlukan produk", retryable=False)
            if not brief["usable_for_promotion"]:
                raise ExecutorError("product_not_cleared", "Produk belum diizinkan dipromosikan: " + "; ".join(brief["blocked_reasons"]), retryable=False)
            comp = s.get(Company, lead.company_id)
            company_name, lead_id = comp.name, lead.id
            s.commit()                           # menyimpan audit pembacaan data pribadi

        claims = "\n".join(f"- {c['text']}" for c in brief["claims"]) or "- (belum ada klaim terverifikasi; jangan menyebut fitur)"
        facts = "\n".join([
            f"Produk: {brief['product']['name']} ({brief['version']['version']})", f"Deskripsi: {brief['product'].get('description') or '-'}",
            f"Klaim terverifikasi:\n{claims}", f"Keterbatasan: {'; '.join(brief['limitations']) or '-'}",
            f"Label: {brief['promotion_label']}", f"Disclaimer wajib: {' '.join(brief['required_disclaimers']) or '-'}"])
        base_prompt = (f"{facts}\n\nPenerima: {pii['name'] or 'Bapak/Ibu'} ({pii['title'] or '-'}) di {company_name}.\n"
                       "Tulis email pengantar singkat (maks. 120 kata) dalam bahasa Indonesia yang sopan. HANYA gunakan fakta di atas. "
                       "Jangan menyebut harga, jangan memakai klaim mutlak (100%, terbaik, dijamin), jangan menyiratkan produk sudah rilis kecuali labelnya RILIS. "
                       "Jangan menulis kalimat berhenti-berlangganan (ditambahkan otomatis). Balas HANYA JSON {subject, body}.")
        system = "Kamu adalah Sales & Client Relations Agent yang jujur. Kamu hanya memakai informasi produk resmi yang diberikan."
        draft, check, feedback = None, None, None
        for _ in range(3):                     # satu penulisan + dua koreksi berdasarkan temuan linter
            res = await ctx.generate(system, base_prompt + (f"\n\nDraf sebelumnya ditolak karena: {feedback}\nPerbaiki." if feedback else ""),
                                     max_tokens=700, json_schema=OUTREACH_SCHEMA)
            try:
                if res.truncated:
                    raise ValueError("jawaban terpotong")
                draft = OutreachOut.model_validate(extract_json(res.text))
            except (ValidationError, ValueError) as e:
                feedback = f"format tidak valid: {str(e)[:200]}"
                draft = None
                continue
            check = check_claims(f"{draft.subject}\n{draft.body}", brief)
            if check["ok"]:
                break
            feedback = "; ".join(f"{f['detail']} ({f.get('match') or ''})" for f in check["findings"] if f["severity"] == "blocking")[:600]
        if draft is None:
            raise ExecutorError("invalid_outreach_output", f"Keluaran draf tidak valid: {feedback}")

        ok = bool(check and check["ok"])
        body = draft.body.strip() + OPT_OUT_FOOTER
        with ctx.session_factory() as s:
            lead = s.get(Lead, lead_id)
            row = service.create_outreach(s, lead, actor=actor, product_id=brief["product"]["id"], version_id=brief["version"]["id"],
                                          channel=p.get("channel") or "email", subject=draft.subject.strip(), body=body,
                                          status="ready_for_review" if ok else "blocked_by_claim_check",
                                          claim_check=check, task_id=ctx.task.id)
            s.commit()
            oid = row.id
        text = "Draf outreach siap ditinjau CEO" if ok else "Draf diblokir pemeriksaan klaim; perlu ditulis ulang manusia"
        return ExecutorOutcome(output=text, verified=ok,
                               verification={"method": "claim_lint", "passed": ok, "findings": (check or {}).get("findings", [])},
                               result={"output": text, "outreach_id": oid, "status": "ready_for_review" if ok else "blocked_by_claim_check"})


# ------------------------------------------------------------------ tindakan eksternal: hanya setelah approval, berhenti di kotak keluar

def _enqueue_outbound(ctx: ExecutionContext, kind: str, actor: str) -> ExecutorOutcome:
    """Eksekusi tindakan eksternal yang SUDAH disetujui CEO. Seluruh syarat diperiksa ulang; hasilnya hanya masuk kotak keluar."""
    p = _params(ctx)
    policy = _policy(ctx)
    with ctx.session_factory() as s:
        try:
            if kind == "content":
                asset = s.get(ContentAsset, p.get("content_id") or "")
                if asset is None:
                    raise ExecutorError("content_not_found", "Konten tidak ditemukan", retryable=False)
                msg = external.enqueue_publish(s, policy, asset, task_id=ctx.task.id, expected_hash=p.get("body_hash") or "", actor=actor)
            else:
                outreach = s.get(OutreachRecord, p.get("outreach_id") or "")
                if outreach is None:
                    raise ExecutorError("outreach_not_found", "Draf outreach tidak ditemukan", retryable=False)
                msg = external.enqueue_outreach(s, policy, outreach, task_id=ctx.task.id, expected_hash=p.get("body_hash") or "", actor=actor)
        except (service.MarketingError, AccessDenied, PolicyError) as e:
            s.rollback()
            raise ExecutorError(getattr(e, "code", "denied"), str(e), retryable=False) from e
        s.commit()
        mid = msg.id
    text = "Masuk kotak keluar. Belum terkirim: CEO yang mengirim secara manual lalu mencatatnya."
    return ExecutorOutcome(output=text, verified=True, verification={"method": "approval_and_policy_recheck", "passed": True},
                           result={"output": text, "outbound_id": mid})


CONTENT_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}}, "required": ["title", "body"]}


class ContentOut(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=30, max_length=20000)


class ContentPromotionExecutor:
    idempotent = False

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if ctx.task.action_type == "publish":
            return _enqueue_outbound(ctx, "content", "content_promotion")
        if ctx.task.action_type != "draft_content":
            raise ExecutorError("unsupported_action", "Content & Promotion hanya mengerjakan draft_content atau publish", retryable=False)
        p = _params(ctx)
        policy = _policy(ctx)
        kind, channel, angle = p.get("kind"), p.get("channel"), (p.get("angle") or "").strip()
        if kind not in external.CONTENT_KINDS:
            raise ExecutorError("invalid_kind", f"Jenis konten harus salah satu dari {external.CONTENT_KINDS}", retryable=False)
        if channel not in policy.content_channels:
            raise ExecutorError("channel_not_allowed", f"Kanal '{channel}' tidak diizinkan", retryable=False)
        try:
            assert_clean(angle=angle)
        except PolicyError as e:
            raise ExecutorError("sensitive_data", e.message, retryable=False) from e
        with ctx.session_factory() as s:
            try:
                brief = external.load_brief(s, p.get("product_id"), p.get("version_id"))
            except service.MarketingError as e:
                raise ExecutorError(e.code, e.message, retryable=False) from e
        if not brief["usable_for_promotion"]:
            raise ExecutorError("product_not_cleared", "Produk belum diizinkan dipromosikan: " + "; ".join(brief["blocked_reasons"]), retryable=False)

        claims = "\n".join(f"- {c['text']}" for c in brief["claims"]) or "- (belum ada klaim terverifikasi; jangan menyebut fitur)"
        facts = "\n".join([
            f"Produk: {brief['product']['name']} ({brief['version']['version']})", f"Deskripsi: {brief['product'].get('description') or '-'}",
            f"Target pelanggan: {brief['product'].get('target_customers') or '-'}", f"Klaim terverifikasi:\n{claims}",
            f"Keterbatasan: {'; '.join(brief['limitations']) or '-'}", f"Label: {brief['promotion_label']}",
            f"Disclaimer wajib: {' '.join(brief['required_disclaimers']) or '-'}"])
        base = (f"{facts}\n\nBuat konten jenis {kind} untuk kanal {channel}." + (f" Sudut pandang: {angle}." if angle else "") +
                " Bahasa Indonesia, ringkas. HANYA gunakan fakta di atas. Jangan menyebut harga, jangan memakai klaim mutlak (100%, terbaik, dijamin, "
                "tanpa bug), jangan menyiratkan produk sudah rilis kecuali labelnya RILIS, dan sebutkan bahwa produk beta jika labelnya BETA. "
                "Balas HANYA JSON {title, body}.")
        system = "Kamu adalah Content & Promotion Agent yang jujur. Kamu hanya memakai informasi produk resmi yang diberikan, tidak pernah mengarang fitur."
        draft, feedback, check = None, None, None
        for _ in range(3):
            res = await ctx.generate(system, base + (f"\n\nDraf sebelumnya ditolak karena: {feedback}\nPerbaiki." if feedback else ""),
                                     max_tokens=900, json_schema=CONTENT_SCHEMA)
            try:
                if res.truncated:
                    raise ValueError("jawaban terpotong")
                draft = ContentOut.model_validate(extract_json(res.text))
            except (ValidationError, ValueError) as e:
                feedback, draft = f"format tidak valid: {str(e)[:200]}", None
                continue
            check = external.lint_text(brief, f"{draft.title}\n{draft.body}")
            if check["ok"]:
                break
            feedback = "; ".join(f"{f['detail']} ({f.get('match') or ''})" for f in check["findings"] if f["severity"] == "blocking")[:600]
        if draft is None:
            raise ExecutorError("invalid_content_output", f"Keluaran konten tidak valid: {feedback}")

        with ctx.session_factory() as s:
            try:
                asset = external.create_content(s, policy, actor="content_promotion", product_id=p["product_id"], version_id=brief["version"]["id"], kind=kind,
                                                channel=channel, title=draft.title, body=draft.body, campaign_id=p.get("campaign_id"), task_id=ctx.task.id)
            except (service.MarketingError, PolicyError, AccessDenied) as e:
                s.rollback()
                raise ExecutorError(getattr(e, "code", "denied"), str(e), retryable=False) from e
            s.commit()
            aid, status = asset.id, asset.status
        ok = status == "ready_for_review"
        text = "Konten siap ditinjau CEO" if ok else "Konten diblokir pemeriksaan klaim; perlu ditulis ulang manusia"
        return ExecutorOutcome(output=text, verified=ok, verification={"method": "claim_lint", "passed": ok, "findings": (check or {}).get("findings", [])},
                               result={"output": text, "content_id": aid, "status": status})
