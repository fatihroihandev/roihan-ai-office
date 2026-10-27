from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, IdMixin, utcnow


class AuditLog(IdMixin, Base):
    """Catatan audit. Append-only: update dan delete ditolak."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    actor: Mapped[str] = mapped_column()
    action: Mapped[str] = mapped_column()
    entity_type: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[str | None] = mapped_column(default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)


class Project(IdMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")  # active | archived
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ProjectFile(IdMixin, Base):
    __tablename__ = "project_files"
    __table_args__ = (Index("ix_project_files_project", "project_id"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column()  # master | requirement | reference | asset
    original_name: Mapped[str] = mapped_column()
    stored_name: Mapped[str] = mapped_column()
    relative_path: Mapped[str] = mapped_column()  # relatif terhadap folder proyek
    content_type: Mapped[str] = mapped_column()
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ModelCapability(IdMixin, Base):
    """Registri kemampuan model. Nilai None berarti belum diketahui (tidak diasumsikan)."""

    __tablename__ = "model_capabilities"
    __table_args__ = (UniqueConstraint("provider", "model_id", name="uq_model_provider_model"),)

    provider: Mapped[str] = mapped_column()
    model_id: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column(default=True)
    is_paid: Mapped[bool] = mapped_column(default=False)
    context_limit: Mapped[int | None] = mapped_column(default=None)
    max_output: Mapped[int | None] = mapped_column(default=None)
    supports_tools: Mapped[bool | None] = mapped_column(default=None)
    supports_structured: Mapped[bool | None] = mapped_column(default=None)
    supports_vision: Mapped[bool | None] = mapped_column(default=None)
    supports_streaming: Mapped[bool | None] = mapped_column(default=None)
    cost_estimate_idr_per_1k: Mapped[float | None] = mapped_column(Float, default=None)
    validation_status: Mapped[str] = mapped_column(default="unvalidated")  # unvalidated | benchmarked
    benchmark: Mapped[dict | None] = mapped_column(JSON, default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelUsage(IdMixin, Base):
    """Log pemanggilan model. Append-only. Isi prompt tidak disimpan, hanya hash dan panjangnya."""

    __tablename__ = "model_usage"
    __table_args__ = (Index("ix_model_usage_created", "created_at"),)

    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    purpose: Mapped[str] = mapped_column(default="adhoc")
    status: Mapped[str] = mapped_column()  # ok | error | blocked | cancelled
    error_kind: Mapped[str | None] = mapped_column(default=None)
    request_id: Mapped[str | None] = mapped_column(default=None)
    correlation_id: Mapped[str | None] = mapped_column(default=None)
    prompt_sha256: Mapped[str | None] = mapped_column(default=None)
    prompt_chars: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(default=None)
    completion_tokens: Mapped[int | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    is_paid: Mapped[bool] = mapped_column(default=False)
    cost_idr: Mapped[float] = mapped_column(Float, default=0.0)


class Task(IdMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status", "status"), Index("ix_tasks_project", "project_id"))

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), default=None)
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column()
    action_type: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
    priority: Mapped[int] = mapped_column(default=0)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(default="low")
    requires_approval: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[bool] = mapped_column(default=False)  # diisi oleh Approval Center (Phase 6)
    difficulty_factors: Mapped[dict | None] = mapped_column(JSON, default=None)
    difficulty_score: Mapped[float | None] = mapped_column(Float, default=None)
    difficulty_category: Mapped[str | None] = mapped_column(default=None)
    preferred_model: Mapped[str | None] = mapped_column(default=None)
    requires_tools: Mapped[bool] = mapped_column(default=False)
    attempt_count: Mapped[int] = mapped_column(default=0)
    attempts_baseline: Mapped[int] = mapped_column(default=0)  # retry manual memberi jatah retry otomatis baru
    max_retries: Mapped[int] = mapped_column(default=2)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    blocked_reason: Mapped[str | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_error_kind: Mapped[str | None] = mapped_column(default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    verification: Mapped[dict | None] = mapped_column(JSON, default=None)
    review_status: Mapped[str | None] = mapped_column(default=None)  # approved | changes_requested (diisi Reviewer)
    params: Mapped[dict | None] = mapped_column(JSON, default=None)  # rujukan terstruktur untuk executor (mis. lead_id, product_id)
    created_by: Mapped[str] = mapped_column(default="ceo")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True)


class TaskAttempt(IdMixin, Base):
    __tablename__ = "task_attempts"
    __table_args__ = (Index("ix_task_attempts_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="running")  # running|succeeded|failed|interrupted|cancelled|blocked
    error_kind: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    retryable: Mapped[bool | None] = mapped_column(default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    provider: Mapped[str | None] = mapped_column(default=None)
    model: Mapped[str | None] = mapped_column(default=None)
    usage: Mapped[dict | None] = mapped_column(JSON, default=None)


class TaskEvent(Base):
    """Jejak kejadian task. `seq` monoton naik dan dipakai klien untuk mendeteksi event yang terlewat."""

    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task", "task_id"), {"sqlite_autoincrement": True})

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String)
    project_id: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column()
    from_status: Mapped[str | None] = mapped_column(default=None)
    to_status: Mapped[str | None] = mapped_column(default=None)
    reason: Mapped[str | None] = mapped_column(default=None)
    actor: Mapped[str] = mapped_column(default="system")
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoutingDecision(IdMixin, Base):
    __tablename__ = "routing_decisions"
    __table_args__ = (Index("ix_routing_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    difficulty_score: Mapped[float | None] = mapped_column(Float, default=None)
    difficulty_category: Mapped[str | None] = mapped_column(default=None)
    risk_level: Mapped[str] = mapped_column(default="low")
    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    num_ctx: Mapped[int] = mapped_column()
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    reasons: Mapped[list] = mapped_column(JSON, default=list)


class Execution(IdMixin, Base):
    """Log eksekusi perintah di sandbox (Bagian 14.1): perintah, waktu, status, exit code. Append-only."""

    __tablename__ = "executions"
    __table_args__ = (Index("ix_executions_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    project_id: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()  # pytest | python_file | compile
    argv: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column()  # ok | failed | timeout | error
    exit_code: Mapped[int | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    timed_out: Mapped[bool] = mapped_column(default=False)
    output_truncated: Mapped[bool] = mapped_column(default=False)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    sandbox: Mapped[str] = mapped_column(default="")


class TestRun(IdMixin, Base):
    __test__ = False  # bukan kelas tes pytest
    __tablename__ = "test_runs"
    __table_args__ = (Index("ix_test_runs_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("executions.id", ondelete="RESTRICT"), default=None)
    project_id: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column()  # passed | failed | error
    source: Mapped[str] = mapped_column(default="junit")  # junit | stdout | none
    total: Mapped[int] = mapped_column(default=0)
    passed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int | None] = mapped_column(default=None)


class TestResult(IdMixin, Base):
    __test__ = False
    __tablename__ = "test_results"
    __table_args__ = (Index("ix_test_results_run", "test_run_id"),)

    test_run_id: Mapped[str] = mapped_column(ForeignKey("test_runs.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column()
    classname: Mapped[str | None] = mapped_column(default=None)
    outcome: Mapped[str] = mapped_column()  # passed | failed | error | skipped
    message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)


class Approval(IdMixin, Base):
    """Persetujuan manusia untuk satu tindakan spesifik (Bagian 12.5). Terikat pada sidik jari isi task."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_task", "task_id"), Index("ix_approvals_status", "status"))

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column(default="task_execution")
    action_type: Mapped[str] = mapped_column()
    risk_level: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="pending")  # pending|approved|rejected|expired|cancelled
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column()
    requested_by: Mapped[str] = mapped_column(default="system")
    decided_by: Mapped[str | None] = mapped_column(default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_reason: Mapped[str | None] = mapped_column(Text, default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CodeReview(IdMixin, Base):
    """Hasil review independen. Append-only."""

    __tablename__ = "code_reviews"
    __table_args__ = (Index("ix_code_reviews_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))  # task Reviewer
    project_id: Mapped[str] = mapped_column()
    reviewed_task_ids: Mapped[list] = mapped_column(JSON, default=list)
    commit: Mapped[str | None] = mapped_column(default=None)
    verdict: Mapped[str] = mapped_column()  # approved | changes_requested
    summary: Mapped[str] = mapped_column(Text, default="")
    verdict_reasons: Mapped[list] = mapped_column(JSON, default=list)
    criteria: Mapped[list] = mapped_column(JSON, default=list)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    unresolved_risks: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class Product(IdMixin, Base):
    """Katalog produk (Bagian 5.3). `line` membedakan jalur bisnis: produk milik sendiri atau layanan pengembangan."""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column()
    line: Mapped[str] = mapped_column(default="owned_product")  # owned_product | service
    description: Mapped[str | None] = mapped_column(Text, default=None)
    target_customers: Mapped[str | None] = mapped_column(Text, default=None)
    pricing_model: Mapped[str | None] = mapped_column(Text, default=None)
    pricing_approved_value: Mapped[str | None] = mapped_column(Text, default=None)  # isi harga yang disetujui CEO
    pricing_approved_by: Mapped[str | None] = mapped_column(default=None)
    pricing_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ProductVersion(IdMixin, Base):
    __tablename__ = "product_versions"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_product_version"), Index("ix_product_versions_product", "product_id"))

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    version: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")  # draft|in_development|internal_testing|beta|released|deprecated|archived
    release_notes: Mapped[str | None] = mapped_column(Text, default=None)
    commit: Mapped[str | None] = mapped_column(default=None)  # commit workspace yang menjadi dasar klaim versi ini
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    limitations_confirmed: Mapped[bool] = mapped_column(default=False)  # CEO menyatakan memang tidak ada batasan yang diketahui
    materials_reviewed: Mapped[bool] = mapped_column(default=False)
    materials_reviewed_by: Mapped[str | None] = mapped_column(default=None)
    materials_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    marketing_permission: Mapped[str] = mapped_column(default="not_allowed")  # not_allowed | beta_only | allowed (izin yang diberikan CEO)
    permission_granted_by: Mapped[str | None] = mapped_column(default=None)
    permission_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    permission_reason: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProductFeature(IdMixin, Base):
    """Klaim fitur. Hanya `verified` (bukti sistem) dan `attested` (pernyataan CEO beralasan) yang boleh dipromosikan."""

    __tablename__ = "product_features"
    __table_args__ = (Index("ix_product_features_version", "version_id"),)

    version_id: Mapped[str] = mapped_column(ForeignKey("product_versions.id", ondelete="RESTRICT"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="unverified")  # verified|attested|unverified|disputed|withdrawn
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    attested_by: Mapped[str | None] = mapped_column(default=None)
    attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    attestation_reason: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProductReleaseCheck(IdMixin, Base):
    """Riwayat evaluasi Product Release Gate. Append-only (termasuk evaluasi yang menolak)."""

    __tablename__ = "product_release_checks"
    __table_args__ = (Index("ix_release_checks_version", "version_id"),)

    version_id: Mapped[str] = mapped_column(ForeignKey("product_versions.id", ondelete="RESTRICT"))
    target: Mapped[str] = mapped_column()  # beta_only | allowed
    ready: Mapped[bool] = mapped_column()
    items: Mapped[list] = mapped_column(JSON, default=list)
    evaluated_by: Mapped[str] = mapped_column(default="system")


class Company(IdMixin, Base):
    """Data tingkat perusahaan (bukan data pribadi). Dedupe lewat normalized_name."""

    __tablename__ = "companies"
    __table_args__ = (Index("ix_companies_norm", "normalized_name"), Index("ix_companies_domain", "domain"))

    name: Mapped[str] = mapped_column()
    normalized_name: Mapped[str] = mapped_column()
    domain: Mapped[str | None] = mapped_column(default=None)
    industry: Mapped[str | None] = mapped_column(default=None)
    size_band: Mapped[str] = mapped_column(default="unknown")  # micro | small | medium | large | unknown
    city: Mapped[str | None] = mapped_column(default=None)
    website: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LeadSource(IdMixin, Base):
    """Provenance prospek: dari mana, kapan, oleh siapa, dengan cara apa (Bagian 4.4 B)."""

    __tablename__ = "lead_sources"

    source_type: Mapped[str] = mapped_column()
    url: Mapped[str | None] = mapped_column(Text, default=None)
    title: Mapped[str | None] = mapped_column(default=None)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collected_by: Mapped[str] = mapped_column()
    method: Mapped[str] = mapped_column(default="manual")  # manual | agent_extraction
    note: Mapped[str | None] = mapped_column(Text, default=None)


class Lead(IdMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_status", "status"), Index("ix_leads_email_hash", "email_hash"), Index("ix_leads_company", "company_id"))

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    source_id: Mapped[str] = mapped_column(ForeignKey("lead_sources.id", ondelete="RESTRICT"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), default=None)
    status: Mapped[str] = mapped_column(default="new")
    score: Mapped[int | None] = mapped_column(default=None)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, default=None)
    basis: Mapped[str] = mapped_column()  # dasar pemrosesan: legitimate_interest_b2b | inbound_inquiry | consent
    owner: Mapped[str] = mapped_column(default="lead_generation")
    contact_name: Mapped[str | None] = mapped_column(default=None)
    contact_title: Mapped[str | None] = mapped_column(default=None)
    contact_email: Mapped[str | None] = mapped_column(default=None)
    contact_phone: Mapped[str | None] = mapped_column(default=None)
    email_hash: Mapped[str | None] = mapped_column(default=None)
    do_not_contact: Mapped[bool] = mapped_column(default=False)
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(default="ceo")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LeadInteraction(IdMixin, Base):
    """Interaksi NYATA dengan prospek. Hanya manusia yang dapat mencatat. Isinya hanya diubah oleh anonimisasi (retensi/penghapusan)."""

    __tablename__ = "lead_interactions"
    __table_args__ = (Index("ix_lead_interactions_lead", "lead_id"),)

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column()  # note | email_out | email_in | call | meeting
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text, default="")
    recorded_by: Mapped[str] = mapped_column()


class SuppressionEntry(IdMixin, Base):
    """Daftar jangan-hubungi. Hanya menyimpan hash, bukan data aslinya. Disimpan permanen (Bagian 15)."""

    __tablename__ = "suppression_entries"
    __table_args__ = (UniqueConstraint("kind", "value_hash", name="uq_suppression"),)

    kind: Mapped[str] = mapped_column()  # email | domain
    value_hash: Mapped[str] = mapped_column()
    reason: Mapped[str] = mapped_column(default="opt_out")  # opt_out | erasure | bounce | complaint


class SalesOpportunity(IdMixin, Base):
    __tablename__ = "sales_opportunities"
    __table_args__ = (Index("ix_opportunities_lead", "lead_id"),)

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column()
    stage: Mapped[str] = mapped_column(default="qualification")  # qualification|proposal|negotiation|won|lost
    value_estimate_idr: Mapped[int | None] = mapped_column(default=None)
    won_value_idr: Mapped[int | None] = mapped_column(default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    outcome_reason: Mapped[str | None] = mapped_column(Text, default=None)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(default="ceo")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ClientRequirement(IdMixin, Base):
    __tablename__ = "client_requirements"
    __table_args__ = (Index("ix_requirements_opportunity", "opportunity_id"),)

    opportunity_id: Mapped[str] = mapped_column(ForeignKey("sales_opportunities.id", ondelete="RESTRICT"))
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(default="normal")  # low | normal | high
    status: Mapped[str] = mapped_column(default="new")  # new | clarified | forwarded
    recorded_by: Mapped[str] = mapped_column(default="ceo")


class MarketResearch(IdMixin, Base):
    """Hasil riset pasar. Setiap temuan menyatakan dasarnya; yang tidak berdasar materi nyata ditandai belum terverifikasi."""

    __tablename__ = "market_research"
    __table_args__ = (Index("ix_market_research_task", "task_id"),)

    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), default=None)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), default=None)
    topic: Mapped[str] = mapped_column()
    summary: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    verified_count: Mapped[int] = mapped_column(default=0)
    unverified_count: Mapped[int] = mapped_column(default=0)


class OutreachRecord(IdMixin, Base):
    """Draf outreach. Belum ada konektor kirim: status `sent_manual` hanya dicatat oleh CEO setelah mengirim sendiri."""

    __tablename__ = "outreach_records"
    __table_args__ = (Index("ix_outreach_lead", "lead_id"),)

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), default=None)
    version_id: Mapped[str | None] = mapped_column(default=None)
    task_id: Mapped[str | None] = mapped_column(default=None)
    channel: Mapped[str] = mapped_column(default="email")
    subject: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(default="draft")  # draft|blocked_by_claim_check|ready_for_review|sent_manual|cancelled
    claim_check: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_by: Mapped[str] = mapped_column(default="sales_client_relations")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sent_note: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Campaign(IdMixin, Base):
    """Kampanye internal. Belum mendukung iklan berbayar: anggaran harus 0 (iklan berbayar memerlukan approval eksplisit dan batas biaya)."""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column()
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    version_id: Mapped[str | None] = mapped_column(default=None)
    objective: Mapped[str] = mapped_column(Text, default="")
    channels: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="draft")  # draft | active | completed | cancelled
    starts_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    budget_idr: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(default="ceo")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContentAsset(IdMixin, Base):
    """Materi konten. Informasi produk hanya dari marketing_brief; keluar dari draft hanya jika lolos linter klaim."""

    __tablename__ = "content_assets"
    __table_args__ = (Index("ix_content_campaign", "campaign_id"),)

    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id", ondelete="RESTRICT"), default=None)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    version_id: Mapped[str | None] = mapped_column(default=None)
    task_id: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column()  # social_post | article | landing_page | demo_script | newsletter
    channel: Mapped[str] = mapped_column()
    title: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text, default="")
    body_hash: Mapped[str] = mapped_column(default="")
    # draft | blocked_by_claim_check | ready_for_review | queued_for_dispatch | published_manual | cancelled
    status: Mapped[str] = mapped_column(default="draft")
    claim_check: Mapped[dict | None] = mapped_column(JSON, default=None)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(default="content_promotion")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CampaignMetric(IdMixin, Base):
    """Angka kinerja yang dicatat manusia. Tidak ada angka yang dikarang atau diperkirakan sistem."""

    __tablename__ = "campaign_metrics"
    __table_args__ = (Index("ix_campaign_metrics_campaign", "campaign_id"),)

    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="RESTRICT"))
    metric: Mapped[str] = mapped_column()  # impressions | clicks | replies | leads | cost_idr | revenue_idr
    value: Mapped[int] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text, default=None)
    recorded_by: Mapped[str] = mapped_column()


class OutboundMessage(IdMixin, Base):
    """Kotak keluar (outbox). Tindakan eksternal yang sudah disetujui berhenti di sini: tidak ada konektor yang mengirim sendiri."""

    __tablename__ = "outbound_messages"
    __table_args__ = (Index("ix_outbound_ref", "kind", "ref_id"), Index("ix_outbound_lead", "lead_id"))

    kind: Mapped[str] = mapped_column()  # content | outreach
    ref_id: Mapped[str] = mapped_column()
    lead_id: Mapped[str | None] = mapped_column(default=None)
    channel: Mapped[str] = mapped_column()
    subject: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text, default="")
    body_hash: Mapped[str] = mapped_column()
    task_id: Mapped[str] = mapped_column()
    approval_id: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="queued_manual")  # queued_manual | dispatched_manual | cancelled
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    dispatched_by: Mapped[str | None] = mapped_column(default=None)


class ClientHandoff(IdMixin, Base):
    """Penyerahan kebutuhan klien dari Sales ke Engineering. Satu peluang menang hanya dapat diserahkan sekali."""

    __tablename__ = "client_handoffs"

    opportunity_id: Mapped[str] = mapped_column(ForeignKey("sales_opportunities.id", ondelete="RESTRICT"), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    task_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(default="ceo")


class PowerState(Base):
    """Status operasional global kantor (Addendum v2.3, Bagian 29.A). Satu baris (id = 1); database adalah sumber kebenaran."""

    __tablename__ = "power_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(default="RUNNING")  # RUNNING | PAUSING | PAUSED | RESUMING | RECOVERY_REQUIRED | ERROR
    shutdown_clean: Mapped[bool] = mapped_column(default=True)  # False selama proses hidup; True hanya setelah shutdown bersih
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    active_command_id: Mapped[str | None] = mapped_column(default=None)
    detail: Mapped[dict | None] = mapped_column(JSON, default=None)  # progres langkah terakhir
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PowerCommand(IdMixin, Base):
    """Permintaan OFF/ON dari CEO beserta progres dan hasilnya."""

    __tablename__ = "power_commands"

    action: Mapped[str] = mapped_column()  # off | on
    requested_by: Mapped[str] = mapped_column(default="ceo")
    status: Mapped[str] = mapped_column(default="accepted")  # accepted | running | completed | failed
    params: Mapped[dict | None] = mapped_column(JSON, default=None)
    progress: Mapped[list] = mapped_column(JSON, default=list)  # [{at, step, status, detail}]
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TaskCheckpoint(IdMixin, Base):
    """Checkpoint keadaan kerja task yang dapat diverifikasi. Tanpa rahasia; `payload_sha256` melindungi integritas isi."""

    __tablename__ = "task_checkpoints"
    __table_args__ = (Index("ix_task_checkpoints_task", "task_id", "created_at"),)

    project_id: Mapped[str] = mapped_column()
    task_id: Mapped[str] = mapped_column()
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    agent_role: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()  # start | periodic | pause | end
    schema_version: Mapped[int] = mapped_column(default=1)
    task_status: Mapped[str] = mapped_column()
    last_step: Mapped[str | None] = mapped_column(default=None)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_sha256: Mapped[str] = mapped_column()
    validation: Mapped[dict | None] = mapped_column(JSON, default=None)  # hasil validasi terakhir {valid, problems, warnings, checked_at}


class RecoveryLog(IdMixin, Base):
    """Riwayat pemulihan: apa yang dilakukan sistem pada tiap task saat resume atau setelah crash."""

    __tablename__ = "recovery_log"
    __table_args__ = (Index("ix_recovery_log_command", "command_id"),)

    command_id: Mapped[str | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(default="resume")  # resume | startup_crash | pause
    task_id: Mapped[str | None] = mapped_column(default=None)
    project_id: Mapped[str | None] = mapped_column(default=None)
    action: Mapped[str] = mapped_column()  # requeued | kept_completed | kept_waiting | manual_required | checkpoint_invalid | ...
    checkpoint_id: Mapped[str | None] = mapped_column(default=None)
    detail: Mapped[dict | None] = mapped_column(JSON, default=None)


class RecoveryItem(IdMixin, Base):
    """Pekerjaan atau operasi yang memerlukan tindakan manusia sebelum sistem kembali RUNNING penuh."""

    __tablename__ = "recovery_items"
    __table_args__ = (Index("ix_recovery_items_status", "status"),)

    task_id: Mapped[str | None] = mapped_column(default=None)
    project_id: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column()  # risky_task_interrupted | external_unknown | files_missing | checkpoint_invalid | no_checkpoint
    reason: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(default="open")  # open | resolved
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolved_by: Mapped[str | None] = mapped_column(default=None)
    resolution: Mapped[str | None] = mapped_column(default=None)  # requeue | cancel | confirmed_done | confirmed_not_done | acknowledged


class ExternalOperation(IdMixin, Base):
    """Operasi ke dunia luar (outreach, publikasi, deployment, pembayaran, pihak ketiga) dengan idempotency key."""

    __tablename__ = "external_operations"

    task_id: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="planned")  # planned | started | confirmed | failed | unknown
    payload_sha256: Mapped[str | None] = mapped_column(default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MarketingArtifact(IdMixin, Base):
    """Artefak SEO/analitik untuk ditinjau (audit, kata kunci, brief, laporan). Hanya usulan: tidak mengubah apa pun di luar."""

    __tablename__ = "marketing_artifacts"
    __table_args__ = (Index("ix_marketing_artifacts_kind", "kind", "created_at"),)

    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), default=None)
    kind: Mapped[str] = mapped_column()  # audit | keywords | brief | analysis
    title: Mapped[str] = mapped_column()
    summary: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_count: Mapped[int] = mapped_column(default=0)
    unverified_count: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(default="seo_specialist")
    handed_off_task_id: Mapped[str | None] = mapped_column(default=None)


class Site(IdMixin, Base):
    """Situs web yang dipasarkan Marketing/SEO. Kode sumbernya disalin ke workspace proyek terkait (folder asli tidak diubah)."""

    __tablename__ = "sites"

    name: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    language: Mapped[str] = mapped_column(default="id")
    source_origin: Mapped[str | None] = mapped_column(default=None)  # lokasi asli kode sumber (hanya catatan)
    status: Mapped[str] = mapped_column(default="active")


class WebRequest(IdMixin, Base):
    """Catatan setiap permintaan web agent (pencarian atau ambil halaman): dasar batas harian dan audit."""

    __tablename__ = "web_requests"
    __table_args__ = (Index("ix_web_requests_created", "created_at"),)

    kind: Mapped[str] = mapped_column()  # search | fetch
    target: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="started")  # started | ok | error
    bytes: Mapped[int] = mapped_column(default=0)
    detail: Mapped[str | None] = mapped_column(default=None)
    task_id: Mapped[str | None] = mapped_column(default=None)


class SeoMetric(IdMixin, Base):
    """Metrik pencarian organik yang dicatat manusia (mis. dari Search Console). Tidak ada angka yang dikarang sistem."""

    __tablename__ = "seo_metrics"

    metric: Mapped[str] = mapped_column()  # impressions | clicks | organic_sessions | conversions | position
    value: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column()  # YYYY-MM atau YYYY-MM-DD
    page: Mapped[str | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    recorded_by: Mapped[str] = mapped_column()


class SeoCampaign(IdMixin, Base):
    """SEO campaign configuration and lifecycle; separate from global task status."""

    __tablename__ = "seo_campaigns"
    __table_args__ = (Index("ix_seo_campaigns_status", "status", "created_at"),)

    name: Mapped[str] = mapped_column(String(160))
    website_url: Mapped[str] = mapped_column(String(1000))
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), default=None)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), default=None)
    target_country: Mapped[str | None] = mapped_column(String(80), default=None)
    target_language: Mapped[str | None] = mapped_column(String(40), default=None)
    target_location: Mapped[str | None] = mapped_column(String(160), default=None)
    primary_keywords: Mapped[list] = mapped_column(JSON, default=list)
    objective: Mapped[str] = mapped_column(Text, default="organic_traffic")
    target_value: Mapped[float | None] = mapped_column(Float, default=None)
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_source: Mapped[str] = mapped_column(Text, default="not_provided")
    starts_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    review_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    api_budget_idr: Mapped[int] = mapped_column(Integer, default=0)
    external_budget_idr: Mapped[int] = mapped_column(Integer, default=0)
    autonomy: Mapped[str] = mapped_column(default="read_only")
    approval_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default="draft")
    created_by: Mapped[str] = mapped_column(default="ceo")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SeoKeyword(IdMixin, Base):
    """Campaign keywords; volume and competition stay null unless a source proves them."""

    __tablename__ = "seo_keywords"
    __table_args__ = (UniqueConstraint("campaign_id", "keyword", name="uq_seo_keyword_campaign_text"),
                      Index("ix_seo_keywords_campaign", "campaign_id", "approval_status"))

    campaign_id: Mapped[str] = mapped_column(ForeignKey("seo_campaigns.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(240))
    intent: Mapped[str] = mapped_column(default="mixed")
    source: Mapped[str] = mapped_column(default="manual")
    rationale: Mapped[str] = mapped_column(Text, default="")
    target_page: Mapped[str | None] = mapped_column(String(1000), default=None)
    volume: Mapped[int | None] = mapped_column(Integer, default=None)
    competition: Mapped[str | None] = mapped_column(String(80), default=None)
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SeoCampaignEvent(IdMixin, Base):
    """Append-only history of campaign edits, decisions, and task handoffs."""

    __tablename__ = "seo_campaign_events"
    __table_args__ = (Index("ix_seo_campaign_events_campaign", "campaign_id", "created_at"),)

    campaign_id: Mapped[str] = mapped_column(ForeignKey("seo_campaigns.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(default="ceo")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class SeoRecommendation(IdMixin, Base):
    """Evidence-backed, human-reviewable work items created from campaign audits."""

    __tablename__ = "seo_recommendations"
    __table_args__ = (UniqueConstraint("campaign_id", "artifact_id", "finding_id", name="uq_seo_recommendation_finding"),
                      Index("ix_seo_recommendations_campaign", "campaign_id", "status", "priority_order"))

    campaign_id: Mapped[str] = mapped_column(ForeignKey("seo_campaigns.id", ondelete="CASCADE"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("marketing_artifacts.id", ondelete="RESTRICT"))
    finding_id: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    impact_basis: Mapped[str] = mapped_column(default="unknown")
    confidence: Mapped[str] = mapped_column(default="observed")
    effort: Mapped[str] = mapped_column(default="unknown")
    risk: Mapped[str] = mapped_column(default="unknown")
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    verification_method: Mapped[str] = mapped_column(Text, default="")
    priority_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(default="proposed")
    decision_note: Mapped[str | None] = mapped_column(Text, default=None)


class OwnerUser(IdMixin, Base):
    """Akun pemilik tunggal platform (Addendum v2.1). Registrasi publik dinonaktifkan."""
    __tablename__ = "owner_users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100), default="Owner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OwnerSession(IdMixin, Base):
    """Sesi login aktif untuk pemilik tunggal (Addendum v2.1)."""
    __tablename__ = "owner_sessions"
    __table_args__ = (Index("ix_owner_sessions_token", "session_token", unique=True),)

    user_id: Mapped[str] = mapped_column(ForeignKey("owner_users.id", ondelete="CASCADE"), index=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _enforce_append_only(session, _ctx, _instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, (AuditLog, ModelUsage, TaskEvent, RoutingDecision, Execution, TestRun, TestResult, CodeReview, ProductReleaseCheck, MarketResearch, SeoCampaignEvent)) and (obj in session.deleted or session.is_modified(obj)):
            raise AppendOnlyError(f"{obj.__tablename__} bersifat append-only")
