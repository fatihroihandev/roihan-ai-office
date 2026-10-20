from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Product, ProductFeature, ProductReleaseCheck, ProductVersion, Project
from app.products import service
from app.products.claims import check_claims
from app.products.service import ProductError
from app.schemas.products import (
    AttestBody, ClaimCheckBody, EvidenceBody, FeatureCreate, PermissionBody, ProductCreate, ProductUpdate, ReasonBody,
    VersionCreate, VersionUpdate,
)
from app.security import require_token
from app.workspace import git as workspace_git

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_token)])
ACTOR = "ceo"  # pemegang token lokal adalah CEO (single-user)
_UNPROCESSABLE = {"invalid_status", "invalid_target", "invalid_permission", "invalid_state", "reason_required"}


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _error(e: ProductError) -> JSONResponse:
    return JSONResponse({"detail": e.message, "code": e.code, **e.details}, status_code=422 if e.code in _UNPROCESSABLE else 409)


def _root(request: Request, product: Product):
    if not product.project_id:
        return None
    return request.app.state.settings.projects_dir / product.project_id / "workspace" / "source-code"


def _product(session: Session, product_id: str) -> Product:
    p = session.get(Product, product_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return p


def _version(session: Session, product: Product, version_id: str) -> ProductVersion:
    v = session.get(ProductVersion, version_id)
    if v is None or v.product_id != product.id:
        raise HTTPException(404, "Versi tidak ditemukan")
    return v


def _feature(session: Session, version: ProductVersion, feature_id: str) -> ProductFeature:
    f = session.get(ProductFeature, feature_id)
    if f is None or f.version_id != version.id:
        raise HTTPException(404, "Fitur tidak ditemukan")
    return f


def _feature_out(f: ProductFeature) -> dict:
    return {"id": f.id, "text": f.text, "status": f.status, "evidence": f.evidence, "attested_by": f.attested_by,
            "attestation_reason": f.attestation_reason, "created_at": service.iso(f.created_at)}


def _version_out(session: Session, product: Product, v: ProductVersion) -> dict:
    feats = list(session.scalars(select(ProductFeature).where(ProductFeature.version_id == v.id).order_by(ProductFeature.created_at, ProductFeature.id)))
    eff = service.effective_permission(session, product, v)
    return {"id": v.id, "version": v.version, "status": v.status, "release_notes": v.release_notes, "commit": v.commit,
            "limitations": v.limitations, "limitations_confirmed": v.limitations_confirmed, "materials_reviewed": v.materials_reviewed,
            "granted_permission": v.marketing_permission, "effective_permission": eff["permission"], "revoked_reasons": eff["revoked_reasons"],
            "permission_granted_by": v.permission_granted_by, "permission_reason": v.permission_reason,
            "features": [_feature_out(f) for f in feats], "created_at": service.iso(v.created_at)}


def _product_out(session: Session, product: Product, with_versions: bool = False) -> dict:
    cur = service.current_version(session, product)
    out = {"id": product.id, "name": product.name, "line": product.line, "description": product.description,
           "target_customers": product.target_customers, "pricing_model": product.pricing_model,
           "pricing_approved": service.pricing_effective(product) is not None, "pricing_approved_by": product.pricing_approved_by,
           "project_id": product.project_id, "status": service.product_status(session, product),
           "current_version": cur.version if cur else None,
           "effective_permission": service.effective_permission(session, product, cur)["permission"] if cur else "not_allowed",
           "created_at": service.iso(product.created_at)}
    if with_versions:
        versions = session.scalars(select(ProductVersion).where(ProductVersion.product_id == product.id)
                                   .order_by(ProductVersion.created_at.desc(), ProductVersion.id))
        out["versions"] = [_version_out(session, product, v) for v in versions]
    return out


# ------------------------------------------------------------------ produk

@router.post("", status_code=201)
def create_product(body: ProductCreate, session: SessionDep):
    if body.project_id:
        proj = session.get(Project, body.project_id)
        if proj is None or proj.deleted_at is not None:
            raise HTTPException(404, "Proyek tidak ditemukan")
    p = Product(**body.model_dump())
    session.add(p)
    session.flush()
    service._audit(session, "product.create", "product", p.id, ACTOR, {"name": p.name, "line": p.line})
    session.commit()
    return _product_out(session, p)


@router.get("")
def list_products(session: SessionDep, line: Literal["owned_product", "service"] | None = None,
                  limit: Annotated[int, Query(ge=1, le=200)] = 100):
    q = select(Product).where(Product.deleted_at.is_(None))
    if line:
        q = q.where(Product.line == line)
    return [_product_out(session, p) for p in session.scalars(q.order_by(Product.created_at.desc()).limit(limit))]


@router.get("/{product_id}")
def get_product(product_id: str, session: SessionDep):
    return _product_out(session, _product(session, product_id), with_versions=True)


@router.patch("/{product_id}")
def update_product(product_id: str, body: ProductUpdate, session: SessionDep):
    p = _product(session, product_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise HTTPException(422, "Nama produk tidak boleh kosong")
    for k, v in changes.items():
        setattr(p, k, v)       # perubahan pricing_model otomatis membatalkan persetujuan harga (lihat pricing_effective)
    service._audit(session, "product.update", "product", p.id, ACTOR, {"fields": sorted(changes)})
    session.commit()
    return _product_out(session, p)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, session: SessionDep):
    p = _product(session, product_id)
    for v in session.scalars(select(ProductVersion).where(ProductVersion.product_id == p.id)):
        v.marketing_permission = "not_allowed"      # produk yang dihapus tidak boleh dipromosikan
    p.deleted_at = utcnow()
    service._audit(session, "product.delete", "product", p.id, ACTOR, {})
    session.commit()


@router.post("/{product_id}/approve-pricing")
def approve_pricing(product_id: str, session: SessionDep, body: ReasonBody | None = None):
    p = _product(session, product_id)
    try:
        service.approve_pricing(session, p, ACTOR, (body or ReasonBody()).reason)
    except ProductError as e:
        return _error(e)
    session.commit()
    return _product_out(session, p)


@router.get("/{product_id}/evidence-candidates")
def evidence_candidates(product_id: str, session: SessionDep):
    return service.evidence_candidates(session, _product(session, product_id))


# ------------------------------------------------------------------ versi

@router.post("/{product_id}/versions", status_code=201)
def create_version(product_id: str, body: VersionCreate, request: Request, session: SessionDep):
    p = _product(session, product_id)
    if session.scalar(select(ProductVersion.id).where(ProductVersion.product_id == p.id, ProductVersion.version == body.version)):
        raise HTTPException(409, f"Versi {body.version} sudah ada")
    commit = None
    if body.pin_commit:
        root = _root(request, p)
        commit = workspace_git.head(root) if root and root.exists() else None
        if commit is None:
            raise HTTPException(409, "Tidak ada commit di workspace proyek untuk di-pin")
    v = ProductVersion(product_id=p.id, version=body.version, release_notes=body.release_notes, commit=commit)
    session.add(v)
    session.flush()
    service._audit(session, "product.version_create", "product_version", v.id, ACTOR, {"version": v.version, "commit": commit})
    session.commit()
    return _version_out(session, p, v)


@router.patch("/{product_id}/versions/{version_id}")
def update_version(product_id: str, version_id: str, body: VersionUpdate, session: SessionDep):
    p, v = _product(session, product_id), None
    v = _version(session, p, version_id)
    ch = body.model_dump(exclude_unset=True)
    try:
        if "status" in ch and ch["status"] is not None:
            service.change_status(session, v, ch.pop("status"), ACTOR)
        else:
            ch.pop("status", None)
        if "materials_reviewed" in ch:
            v.materials_reviewed = bool(ch.pop("materials_reviewed"))
            v.materials_reviewed_by, v.materials_reviewed_at = (ACTOR, utcnow()) if v.materials_reviewed else (None, None)
            service._audit(session, "product.materials_reviewed", "product_version", v.id, ACTOR, {"reviewed": v.materials_reviewed})
        for k, val in ch.items():
            if val is not None:
                setattr(v, k, val)
        if "limitations" in ch and ch["limitations"]:
            v.limitations_confirmed = False     # batasan nyata menggantikan pernyataan "tidak ada batasan"
    except ProductError as e:
        session.rollback()
        return _error(e)
    session.commit()
    return _version_out(session, p, v)


@router.post("/{product_id}/versions/{version_id}/pin-commit")
def pin_commit(product_id: str, version_id: str, request: Request, session: SessionDep):
    p = _product(session, product_id)
    v = _version(session, p, version_id)
    root = _root(request, p)
    head = workspace_git.head(root) if root and root.exists() else None
    if head is None:
        raise HTTPException(409, "Tidak ada commit di workspace proyek untuk di-pin")
    v.commit = head
    for f in session.scalars(select(ProductFeature).where(ProductFeature.version_id == v.id)):
        service.reverify(session, p, v, f, root)       # commit baru dapat mengubah validitas bukti
    service._audit(session, "product.commit_pinned", "product_version", v.id, ACTOR, {"commit": head})
    session.commit()
    return _version_out(session, p, v)


# ------------------------------------------------------------------ fitur (klaim)

@router.post("/{product_id}/versions/{version_id}/features", status_code=201)
def add_feature(product_id: str, version_id: str, body: FeatureCreate, request: Request, session: SessionDep):
    p = _product(session, product_id)
    v = _version(session, p, version_id)
    status, evidence = service.evaluate_feature(session, project_id=p.project_id, version_commit=v.commit, task_ids=body.task_ids, root=_root(request, p))
    f = ProductFeature(version_id=v.id, text=body.text, status=status, evidence=evidence)
    session.add(f)
    session.flush()
    service._audit(session, "product.feature_add", "product_feature", f.id, ACTOR, {"text": f.text, "status": status})
    session.commit()
    return _feature_out(f)


def _feat_ctx(session, product_id, version_id, feature_id):
    p = _product(session, product_id)
    v = _version(session, p, version_id)
    return p, v, _feature(session, v, feature_id)


@router.post("/{product_id}/versions/{version_id}/features/{feature_id}/evidence")
def attach_evidence(product_id: str, version_id: str, feature_id: str, body: EvidenceBody, request: Request, session: SessionDep):
    p, v, f = _feat_ctx(session, product_id, version_id, feature_id)
    if f.status in {"attested", "disputed", "withdrawn"}:
        return _error(ProductError("fixed_state", f"Klaim berstatus {f.status}; bukti tidak mengubah status yang ditetapkan manusia"))
    ids = list(dict.fromkeys([*(f.evidence or {}).get("task_ids", []), *body.task_ids]))
    f.status, f.evidence = service.evaluate_feature(session, project_id=p.project_id, version_commit=v.commit, task_ids=ids, root=_root(request, p))
    session.commit()
    return _feature_out(f)


@router.post("/{product_id}/versions/{version_id}/features/{feature_id}/reverify")
def reverify_feature(product_id: str, version_id: str, feature_id: str, request: Request, session: SessionDep):
    p, v, f = _feat_ctx(session, product_id, version_id, feature_id)
    service.reverify(session, p, v, f, _root(request, p))
    session.commit()
    return _feature_out(f)


@router.post("/{product_id}/versions/{version_id}/features/{feature_id}/attest")
def attest_feature(product_id: str, version_id: str, feature_id: str, body: AttestBody, session: SessionDep):
    _, _, f = _feat_ctx(session, product_id, version_id, feature_id)
    try:
        service.attest(session, f, ACTOR, body.reason)
    except ProductError as e:
        return _error(e)
    session.commit()
    return _feature_out(f)


@router.post("/{product_id}/versions/{version_id}/features/{feature_id}/{state}")
def mark_feature(product_id: str, version_id: str, feature_id: str, state: Literal["dispute", "withdraw"], session: SessionDep,
                 body: ReasonBody | None = None):
    _, _, f = _feat_ctx(session, product_id, version_id, feature_id)
    try:
        service.set_feature_state(session, f, {"dispute": "disputed", "withdraw": "withdrawn"}[state], ACTOR, (body or ReasonBody()).reason)
    except ProductError as e:
        return _error(e)
    session.commit()
    return _feature_out(f)


# ------------------------------------------------------------------ gerbang rilis, izin, brief, linter

@router.get("/{product_id}/versions/{version_id}/release-gate")
def release_gate(product_id: str, version_id: str, session: SessionDep, target: Literal["beta_only", "allowed"] = "beta_only"):
    p = _product(session, product_id)
    return service.evaluate_gate(session, p, _version(session, p, version_id), target)


@router.get("/{product_id}/versions/{version_id}/release-checks")
def release_checks(product_id: str, version_id: str, session: SessionDep):
    p = _product(session, product_id)
    v = _version(session, p, version_id)
    rows = session.scalars(select(ProductReleaseCheck).where(ProductReleaseCheck.version_id == v.id).order_by(ProductReleaseCheck.created_at.desc()))
    return [{"id": r.id, "created_at": service.iso(r.created_at), "target": r.target, "ready": r.ready, "evaluated_by": r.evaluated_by,
             "failed": [i["key"] for i in r.items if i["required"] and not i["passed"]]} for r in rows]


@router.post("/{product_id}/versions/{version_id}/marketing-permission")
def marketing_permission(product_id: str, version_id: str, body: PermissionBody, session: SessionDep):
    p = _product(session, product_id)
    v = _version(session, p, version_id)
    try:
        service.grant_permission(session, p, v, body.permission, ACTOR, body.reason)
    except ProductError as e:
        session.commit()        # evaluasi gerbang yang menolak dan audit-nya tetap disimpan
        return _error(e)
    session.commit()
    return _version_out(session, p, v)


@router.get("/{product_id}/versions/{version_id}/marketing-brief")
def marketing_brief(product_id: str, version_id: str, session: SessionDep):
    p = _product(session, product_id)
    return service.marketing_brief(session, p, _version(session, p, version_id))


@router.post("/{product_id}/versions/{version_id}/check-claims")
def check_marketing_claims(product_id: str, version_id: str, body: ClaimCheckBody, session: SessionDep):
    p = _product(session, product_id)
    return check_claims(body.text, service.marketing_brief(session, p, _version(session, p, version_id)))
