"""Katalog produk dan Product Release Gate (Bagian 5.3).

Prinsip: status pengembangan dan izin pemasaran adalah dua hal berbeda. Izin hanya diberikan CEO, hanya jika gerbang
lulus, dan DIHITUNG ULANG setiap dibaca: jika bukti berubah (fitur disengketakan, status turun, harga berubah) izin
otomatis gugur. Klaim fitur hanya `verified` jika punya bukti Engineering nyata, atau `attested` (pernyataan CEO beralasan).
"""
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals.service import HUMAN_ACTORS
from app.db.base import utcnow
from app.db.models import (
    AuditLog, CodeReview, Product, ProductFeature, ProductReleaseCheck, ProductVersion, Task, TestRun,
)
from app.workspace import git as workspace_git

STATUSES = ["draft", "in_development", "internal_testing", "beta", "released", "deprecated", "archived"]
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_development", "archived"},
    "in_development": {"internal_testing", "draft", "deprecated", "archived"},
    "internal_testing": {"beta", "in_development", "deprecated", "archived"},
    "beta": {"released", "internal_testing", "deprecated", "archived"},
    "released": {"deprecated", "archived"},     # klaim rilis tidak ditarik mundur ke tahap sebelumnya
    "deprecated": {"archived"},
    "archived": set(),
}
PERMISSIONS = ["not_allowed", "beta_only", "allowed"]
REQUIRED_STATUS = {"beta_only": "beta", "allowed": "released"}
USABLE_FEATURE = {"verified", "attested"}
PENDING_FEATURE = {"unverified", "disputed"}


class ProductError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _need_human(actor: str) -> None:
    if actor not in HUMAN_ACTORS:
        raise ProductError("agent_cannot_decide", f"'{actor}' bukan pihak yang berwenang memutuskan hal ini")


def _audit(session: Session, action: str, entity_type: str, entity_id: str, actor: str, details: dict) -> None:
    session.add(AuditLog(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


# ------------------------------------------------------------------ status

def current_version(session: Session, product: Product) -> ProductVersion | None:
    rows = list(session.scalars(select(ProductVersion).where(ProductVersion.product_id == product.id, ProductVersion.status != "archived")
                                .order_by(ProductVersion.created_at.desc(), ProductVersion.id)))
    return rows[0] if rows else None


def product_status(session: Session, product: Product) -> str:
    v = current_version(session, product)
    return v.status if v else "draft"


def change_status(session: Session, version: ProductVersion, new_status: str, actor: str) -> ProductVersion:
    if new_status not in STATUSES:
        raise ProductError("invalid_status", f"Status tidak dikenal: {new_status}")
    if new_status not in TRANSITIONS[version.status]:
        raise ProductError("invalid_transition", f"Perpindahan status {version.status} -> {new_status} tidak diizinkan")
    old = version.status
    version.status = new_status
    # Izin pemasaran yang bergantung pada status lama dicabut secara eksplisit (efektifnya juga dihitung ulang saat dibaca)
    needed = REQUIRED_STATUS.get(version.marketing_permission)
    if version.marketing_permission != "not_allowed" and needed != new_status:
        _audit(session, "product.permission_revoked", "product_version", version.id, "system",
               {"from": version.marketing_permission, "reason": f"status berubah dari {old} ke {new_status}"})
        version.marketing_permission, version.permission_reason = "not_allowed", f"dicabut otomatis: status menjadi {new_status}"
    _audit(session, "product.status_changed", "product_version", version.id, actor, {"from": old, "to": new_status})
    return version


# ------------------------------------------------------------------ bukti klaim fitur

def evaluate_feature(session: Session, *, project_id: str | None, version_commit: str | None, task_ids: list[str],
                     root: Path | None) -> tuple[str, dict]:
    """Klaim `verified` hanya jika ada implementasi selesai+terverifikasi, bukti tes lulus, tidak ada review yang menolak,
    dan commit implementasi termasuk dalam commit versi. Selain itu `unverified` beserta daftar masalahnya."""
    problems: list[str] = []
    infos: list[dict] = []
    ids = list(dict.fromkeys(task_ids))
    if project_id is None:
        problems.append("Produk belum terhubung ke proyek Engineering")
    if not ids:
        problems.append("Tidak ada task bukti yang terhubung")
    impl_commits: list[tuple[str, str]] = []
    impl_ok = tests_ok = False

    for tid in ids if project_id else []:
        t = session.get(Task, tid)
        if t is None or t.project_id != project_id:
            problems.append(f"Task {tid[:8]} tidak ada pada proyek produk")
            continue
        commit = (t.result or {}).get("commit")
        infos.append({"id": t.id, "title": t.title, "role": t.role, "action_type": t.action_type, "status": t.status, "commit": commit})
        if t.status != "completed":
            problems.append(f"Task '{t.title}' belum selesai ({t.status})")
            continue
        if t.role == "developer" and t.action_type == "code_change" and (t.verification or {}).get("passed"):
            impl_ok = True
            if commit:
                impl_commits.append((t.title, commit))
        runs = list(session.scalars(select(TestRun).where(TestRun.task_id == t.id).order_by(TestRun.created_at.desc(), TestRun.id)))
        if runs:
            if runs[0].status == "passed":
                tests_ok = True
            else:
                problems.append(f"Tes terakhir pada task '{t.title}' tidak lulus ({runs[0].status})")

    for r in session.scalars(select(CodeReview).order_by(CodeReview.created_at.desc())) if ids else []:
        if set(r.reviewed_task_ids or []) & set(ids):
            if r.verdict == "changes_requested":
                problems.append("Review independen terbaru meminta perubahan atas task bukti")
            break   # hanya review terbaru yang menentukan

    if project_id and ids and not impl_ok:
        problems.append("Tidak ada task implementasi (developer/code_change) yang selesai dan terverifikasi")
    if project_id and ids and not tests_ok:
        problems.append("Tidak ada bukti tes yang lulus pada task terhubung")
    if impl_commits:
        if not version_commit:
            problems.append("Versi belum di-pin ke commit workspace")
        elif root is None:
            problems.append("Workspace proyek tidak tersedia untuk memeriksa commit")
        else:
            for title, commit in impl_commits:
                if not workspace_git.is_ancestor(root, commit, version_commit):
                    problems.append(f"Commit {commit} dari task '{title}' bukan bagian dari commit versi {version_commit}")
    elif impl_ok and not version_commit:
        problems.append("Versi belum di-pin ke commit workspace")

    status = "verified" if not problems else "unverified"
    return status, {"task_ids": ids, "tasks": infos, "problems": problems, "version_commit": version_commit,
                    "checked_at": utcnow().isoformat()}


def reverify(session: Session, product: Product, version: ProductVersion, feature: ProductFeature, root: Path | None) -> ProductFeature:
    """Hitung ulang bukti. Status yang ditetapkan manusia (attested, disputed, withdrawn) tidak disentuh."""
    if feature.status in {"attested", "disputed", "withdrawn"}:
        return feature
    status, evidence = evaluate_feature(session, project_id=product.project_id, version_commit=version.commit,
                                        task_ids=(feature.evidence or {}).get("task_ids", []), root=root)
    feature.status, feature.evidence = status, evidence
    return feature


def attest(session: Session, feature: ProductFeature, actor: str, reason: str) -> ProductFeature:
    _need_human(actor)
    if len((reason or "").strip()) < 10:
        raise ProductError("reason_required", "Pernyataan manual memerlukan alasan minimal 10 karakter")
    if feature.status == "withdrawn":
        raise ProductError("withdrawn", "Klaim yang ditarik tidak dapat dinyatakan")
    feature.status, feature.attested_by, feature.attested_at, feature.attestation_reason = "attested", actor, utcnow(), reason.strip()
    _audit(session, "product.feature_attested", "product_feature", feature.id, actor, {"reason": reason.strip(), "text": feature.text})
    return feature


def set_feature_state(session: Session, feature: ProductFeature, state: str, actor: str, reason: str | None) -> ProductFeature:
    """disputed: klaim dipertanyakan (tidak boleh dipakai). withdrawn: klaim ditarik."""
    _need_human(actor)
    if state not in {"disputed", "withdrawn"}:
        raise ProductError("invalid_state", "Status harus disputed atau withdrawn")
    feature.status = state
    _audit(session, f"product.feature_{state}", "product_feature", feature.id, actor, {"reason": reason, "text": feature.text})
    return feature


# ------------------------------------------------------------------ pricing

def pricing_effective(product: Product) -> str | None:
    """Harga hanya boleh dipakai jika isinya persis sama dengan yang disetujui CEO (perubahan harga membatalkan persetujuan)."""
    if product.pricing_model and product.pricing_approved_value == product.pricing_model:
        return product.pricing_model
    return None


def approve_pricing(session: Session, product: Product, actor: str, reason: str | None) -> Product:
    _need_human(actor)
    if not (product.pricing_model or "").strip():
        raise ProductError("no_pricing", "Model harga belum diisi")
    product.pricing_approved_value, product.pricing_approved_by, product.pricing_approved_at = product.pricing_model, actor, utcnow()
    _audit(session, "product.pricing_approved", "product", product.id, actor, {"pricing_model": product.pricing_model, "reason": reason})
    return product


# ------------------------------------------------------------------ Release Gate

def _features(session: Session, version: ProductVersion) -> list[ProductFeature]:
    return list(session.scalars(select(ProductFeature).where(ProductFeature.version_id == version.id)
                                .order_by(ProductFeature.created_at, ProductFeature.id)))


def evaluate_gate(session: Session, product: Product, version: ProductVersion, target: str) -> dict:
    if target not in REQUIRED_STATUS:
        raise ProductError("invalid_target", "Target harus beta_only atau allowed")
    feats = [f for f in _features(session, version) if f.status != "withdrawn"]
    usable = [f for f in feats if f.status in USABLE_FEATURE]
    verified = [f for f in feats if f.status == "verified"]
    pending = [f for f in feats if f.status in PENDING_FEATURE]
    full = target == "allowed"
    need = REQUIRED_STATUS[target]

    def item(key, label, passed, detail, required=True):
        return {"key": key, "label": label, "required": required, "passed": bool(passed), "detail": detail}

    items = [
        item("name_version", "Nama dan versi produk", bool(product.name.strip() and version.version.strip()), f"{product.name} {version.version}"),
        item("status_matches", f"Status pengembangan harus '{need}'", version.status == need, f"status saat ini: {version.status}"),
        item("commit_pinned", "Versi terhubung ke commit workspace", bool(version.commit), version.commit or "belum di-pin"),
        item("features_verified", "Ada fitur yang boleh dipromosikan (terverifikasi)", bool(usable),
             f"{len(usable)} fitur terverifikasi, {len(pending)} belum terverifikasi (tidak akan dipromosikan)"),
        item("tests_passed", "Ada bukti tes lulus dari Engineering", bool(verified),
             f"{len(verified)} fitur terverifikasi oleh bukti sistem" if verified else "tidak ada fitur yang dibuktikan oleh tes"),
        item("no_pending_claims", "Tidak ada klaim yang belum terverifikasi atau disengketakan", not pending,
             f"{len(pending)} klaim menunggu: verifikasi, nyatakan beralasan, atau tarik" if pending else "bersih", required=full),
        item("limitations_documented", "Batasan yang diketahui didokumentasikan", bool(version.limitations) or version.limitations_confirmed,
             f"{len(version.limitations)} batasan" if version.limitations else ("CEO menyatakan tidak ada batasan yang diketahui" if version.limitations_confirmed else "belum ada")),
        item("target_customers", "Target pelanggan ditentukan", bool((product.target_customers or "").strip()), product.target_customers or "belum diisi"),
        item("pricing_approved", "Harga atau model bisnis disetujui CEO", pricing_effective(product) is not None,
             "disetujui" if pricing_effective(product) else ("diubah setelah disetujui" if product.pricing_approved_value else "belum disetujui"), required=full),
        item("materials_reviewed", "Materi promosi sudah ditinjau", version.materials_reviewed,
             "ditinjau CEO" if version.materials_reviewed else "belum ditinjau", required=full),
    ]
    return {"target": target, "ready": all(i["passed"] for i in items if i["required"]), "items": items}


def effective_permission(session: Session, product: Product, version: ProductVersion) -> dict:
    """Izin yang berlaku SEKARANG: izin tersimpan hanya berlaku jika gerbangnya masih lulus."""
    granted = version.marketing_permission
    if granted == "not_allowed":
        return {"permission": "not_allowed", "granted": granted, "revoked_reasons": []}
    gate = evaluate_gate(session, product, version, granted)
    if gate["ready"]:
        return {"permission": granted, "granted": granted, "revoked_reasons": []}
    reasons = [f"{i['label']}: {i['detail']}" for i in gate["items"] if i["required"] and not i["passed"]]
    return {"permission": "not_allowed", "granted": granted, "revoked_reasons": reasons}


def grant_permission(session: Session, product: Product, version: ProductVersion, permission: str, actor: str, reason: str | None) -> ProductVersion:
    _need_human(actor)
    if permission not in PERMISSIONS:
        raise ProductError("invalid_permission", f"Izin harus salah satu dari {PERMISSIONS}")
    if permission == "not_allowed":      # mencabut izin selalu boleh
        version.marketing_permission, version.permission_granted_by = "not_allowed", actor
        version.permission_granted_at, version.permission_reason = utcnow(), reason
        _audit(session, "product.permission_revoked", "product_version", version.id, actor, {"reason": reason})
        return version
    gate = evaluate_gate(session, product, version, permission)
    session.add(ProductReleaseCheck(version_id=version.id, target=permission, ready=gate["ready"], items=gate["items"], evaluated_by=actor))
    if not gate["ready"]:
        failed = [i for i in gate["items"] if i["required"] and not i["passed"]]
        _audit(session, "product.permission_refused", "product_version", version.id, actor,
               {"target": permission, "failed": [i["key"] for i in failed]})
        raise ProductError("gate_failed", "Product Release Gate belum lulus: " + "; ".join(i["label"] for i in failed),
                           {"items": gate["items"], "failed": [i["key"] for i in failed]})
    version.marketing_permission, version.permission_granted_by = permission, actor
    version.permission_granted_at, version.permission_reason = utcnow(), reason
    _audit(session, "product.permission_granted", "product_version", version.id, actor, {"permission": permission, "reason": reason})
    return version


# ------------------------------------------------------------------ ringkasan resmi untuk Marketing

def marketing_brief(session: Session, product: Product, version: ProductVersion) -> dict:
    """SATU-SATUNYA sumber informasi produk yang boleh dipakai Marketing. Klaim hanya muncul jika produk diizinkan;
    klaim yang belum terverifikasi selalu dipisahkan dan diberi label."""
    eff = effective_permission(session, product, version)
    usable = eff["permission"] != "not_allowed"
    feats = [f for f in _features(session, version) if f.status != "withdrawn"]
    label = {"beta_only": "BETA", "allowed": "RILIS"}.get(eff["permission"])
    disclaimers = []
    if eff["permission"] == "beta_only":
        disclaimers.append("Produk ini masih dalam tahap beta; fitur dan stabilitas dapat berubah.")
    return {
        "product": {"id": product.id, "name": product.name, "line": product.line, "description": product.description,
                    "target_customers": product.target_customers},
        "version": {"id": version.id, "version": version.version, "status": version.status, "commit": version.commit},
        "effective_permission": eff["permission"], "usable_for_promotion": usable, "promotion_label": label,
        "blocked_reasons": eff["revoked_reasons"] if not usable else [],
        "claims": [{"id": f.id, "text": f.text, "basis": f.status} for f in feats if f.status in USABLE_FEATURE] if usable else [],
        "unverified_claims": [{"id": f.id, "text": f.text, "status": f.status,
                               "label": "BELUM TERVERIFIKASI: jangan dipromosikan sebagai fakta",
                               "problems": (f.evidence or {}).get("problems", [])} for f in feats if f.status in PENDING_FEATURE],
        "limitations": list(version.limitations or []),
        "pricing": pricing_effective(product) if usable else None,
        "required_disclaimers": disclaimers,
    }


def evidence_candidates(session: Session, product: Product) -> list[dict]:
    """Task Engineering selesai pada proyek produk yang dapat dilampirkan sebagai bukti klaim."""
    if not product.project_id:
        return []
    out = []
    for t in session.scalars(select(Task).where(Task.project_id == product.project_id, Task.status == "completed",
                                               Task.role.in_(["developer", "qa", "reviewer"])).order_by(Task.created_at, Task.id)):
        runs = list(session.scalars(select(TestRun).where(TestRun.task_id == t.id).order_by(TestRun.created_at.desc())))
        out.append({"id": t.id, "title": t.title, "role": t.role, "action_type": t.action_type, "review_status": t.review_status,
                    "commit": (t.result or {}).get("commit"), "last_test_status": runs[0].status if runs else None,
                    "last_test_passed": runs[0].passed if runs else None})
    return out


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
