import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLog, ProductReleaseCheck, ProductVersion
from app.main import create_app
from app.products import service
from app.products.service import STATUSES, TRANSITIONS, ProductError
from app.tasks.executors import default_executors
from app.workspace import git
from tests.fakes import FakeProvider, FakeSandbox, pytest_fail, pytest_ok
from tests.test_engineering_agents import CALC, TEST_CALC, gen

QA_TEST = "from calc import add\n\n\ndef test_add_qa():\n    assert add(2, 2) == 4\n"


def make_client(settings, replies=(), sandbox=None):
    cfg = settings.model_copy(update={"ollama_enabled": True, "retry_backoff_base_s": 0.0})
    provider = FakeProvider(reply=list(replies))
    sb = sandbox or FakeSandbox(pytest=[pytest_ok("test_add"), pytest_ok("test_add", "test_add_qa")])
    return TestClient(create_app(cfg, providers={"ollama": provider}, executors=default_executors(), sandbox=sb))


def drain(c):
    for _ in range(20):
        if not asyncio.run(c.app.state.worker.run_once()):
            return


def call(c, auth, method, path, body=None, **kw):
    return getattr(c, method)(path, json=body, headers=auth, **kw) if body is not None else getattr(c, method)(path, headers=auth, **kw)


def mk_task(c, auth, pid, **kw):
    t = c.post("/api/tasks", json={"project_id": pid, **kw}, headers=auth).json()
    c.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    return t["id"]


class Eng:
    """Proyek dengan task Developer dan QA yang benar-benar selesai (bukti Engineering nyata)."""

    def __init__(self, c, auth, pid, dev, qa):
        self.c, self.auth, self.pid, self.dev, self.qa = c, auth, pid, dev, qa


@pytest.fixture
def eng(settings, auth):
    c = make_client(settings, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC)), gen(("tests/test_calc_qa.py", QA_TEST))])
    pid = c.post("/api/projects", json={"name": "Kalkulator"}, headers=auth).json()["id"]
    dev = mk_task(c, auth, pid, title="Fungsi kalkulator", role="developer", action_type="code_change", acceptance_criteria=["add benar"])
    drain(c)
    qa = mk_task(c, auth, pid, title="Uji kalkulator", role="qa", action_type="run_tests", depends_on=[dev], acceptance_criteria=["add diuji"])
    drain(c)
    for t in (dev, qa):
        assert c.get(f"/api/tasks/{t}", headers=auth).json()["status"] == "completed"
    return Eng(c, auth, pid, dev, qa)


def product(e, **kw):
    body = {"name": "Kalkulator Pro", "description": "Kalkulator", "target_customers": "Pelajar", "project_id": e.pid, **kw}
    r = e.c.post("/api/products", json=body, headers=e.auth)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def version(e, pid, v="0.1.0", pin=True):
    r = e.c.post(f"/api/products/{pid}/versions", json={"version": v, "pin_commit": pin}, headers=e.auth)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def feature(e, pid, vid, text="Penjumlahan dua angka", tasks=None):
    r = e.c.post(f"/api/products/{pid}/versions/{vid}/features", json={"text": text, "task_ids": e.dev and (tasks if tasks is not None else [e.dev, e.qa])}, headers=e.auth)
    assert r.status_code == 201, r.text
    return r.json()


def set_status(e, pid, vid, *path):
    for s in path:
        r = e.c.patch(f"/api/products/{pid}/versions/{vid}", json={"status": s}, headers=e.auth)
        assert r.status_code == 200, (s, r.text)


def to_beta(e, pid, vid):
    set_status(e, pid, vid, "in_development", "internal_testing", "beta")


def ready_beta(e):
    pid = product(e)
    vid = version(e, pid)
    f = feature(e, pid, vid)
    e.c.patch(f"/api/products/{pid}/versions/{vid}", json={"limitations": ["Hanya operasi dasar"]}, headers=e.auth)
    to_beta(e, pid, vid)
    return pid, vid, f


def gate(e, pid, vid, target="beta_only"):
    return e.c.get(f"/api/products/{pid}/versions/{vid}/release-gate", params={"target": target}, headers=e.auth).json()


def failed(g):
    return {i["key"] for i in g["items"] if i["required"] and not i["passed"]}


def eff(e, pid, vid):
    return next(v for v in e.c.get(f"/api/products/{pid}", headers=e.auth).json()["versions"] if v["id"] == vid)["effective_permission"]


def grant(e, pid, vid, permission="beta_only", reason="siap"):
    return e.c.post(f"/api/products/{pid}/versions/{vid}/marketing-permission", json={"permission": permission, "reason": reason}, headers=e.auth)


# ================================================================== dasar katalog

def test_every_endpoint_requires_the_token(settings):
    c = make_client(settings)
    for method, path in [("get", "/api/products"), ("post", "/api/products"), ("get", "/api/products/x"), ("patch", "/api/products/x"),
                         ("delete", "/api/products/x"), ("post", "/api/products/x/approve-pricing"), ("get", "/api/products/x/evidence-candidates"),
                         ("post", "/api/products/x/versions"), ("patch", "/api/products/x/versions/y"),
                         ("post", "/api/products/x/versions/y/marketing-permission"), ("get", "/api/products/x/versions/y/marketing-brief"),
                         ("post", "/api/products/x/versions/y/check-claims"), ("get", "/api/products/x/versions/y/release-gate"),
                         ("post", "/api/products/x/versions/y/features"), ("post", "/api/products/x/versions/y/features/z/attest")]:
        assert getattr(c, method)(path).status_code == 401, path


def test_create_list_update_and_validation(eng):
    c, a = eng.c, eng.auth
    pid = product(eng, name="  Produk A  ")
    svc = c.post("/api/products", json={"name": "Jasa Web", "line": "service"}, headers=a).json()
    assert svc["line"] == "service" and svc["status"] == "draft" and svc["effective_permission"] == "not_allowed"
    assert {p["name"] for p in c.get("/api/products", headers=a).json()} == {"Produk A", "Jasa Web"}
    assert [p["name"] for p in c.get("/api/products?line=service", headers=a).json()] == ["Jasa Web"]
    r = c.patch(f"/api/products/{pid}", json={"description": "baru"}, headers=a)
    assert r.json()["description"] == "baru"
    for bad in ({"name": "  "}, {"name": "x" * 121}, {"name": "ok", "line": "lain"}, {}):
        assert c.post("/api/products", json=bad, headers=a).status_code == 422, bad
    assert c.post("/api/products", json={"name": "x", "project_id": "tidak-ada"}, headers=a).status_code == 404
    assert c.get("/api/products/tidak-ada", headers=a).status_code == 404


def test_versions_have_unique_names_and_valid_format(eng):
    pid = product(eng)
    version(eng, pid, "1.0.0", pin=False)
    assert eng.c.post(f"/api/products/{pid}/versions", json={"version": "1.0.0"}, headers=eng.auth).status_code == 409
    for bad in ("", "a b", "../x", "x" * 41, "-1"):
        assert eng.c.post(f"/api/products/{pid}/versions", json={"version": bad}, headers=eng.auth).status_code == 422, bad


def test_pin_commit_requires_a_workspace_commit(settings, auth):
    c = make_client(settings)
    pid = c.post("/api/projects", json={"name": "Kosong"}, headers=auth).json()["id"]
    prod = c.post("/api/products", json={"name": "P", "project_id": pid}, headers=auth).json()["id"]
    assert c.post(f"/api/products/{prod}/versions", json={"version": "1", "pin_commit": True}, headers=auth).status_code == 409
    vid = c.post(f"/api/products/{prod}/versions", json={"version": "1"}, headers=auth).json()["id"]
    assert c.post(f"/api/products/{prod}/versions/{vid}/pin-commit", headers=auth).status_code == 409


def test_pin_commit_records_workspace_head(eng):
    pid = product(eng)
    vid = version(eng, pid)
    head = git.head(eng.c.app.state.settings.projects_dir / eng.pid / "workspace" / "source-code")
    v = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["versions"][0]
    assert v["commit"] == head and head


# Tabel harapan ditulis eksplisit (BUKAN dibaca dari kode produksi) agar perubahan aturan tertangkap tes.
EXPECTED_TRANSITIONS = {
    "draft": {"in_development", "archived"},
    "in_development": {"internal_testing", "draft", "deprecated", "archived"},
    "internal_testing": {"beta", "in_development", "deprecated", "archived"},
    "beta": {"released", "internal_testing", "deprecated", "archived"},
    "released": {"deprecated", "archived"},
    "deprecated": {"archived"},
    "archived": set(),
}


def test_transition_table_is_exactly_the_documented_one():
    assert TRANSITIONS == EXPECTED_TRANSITIONS and list(STATUSES) == list(EXPECTED_TRANSITIONS)
    assert "beta" not in TRANSITIONS["released"] and "draft" not in TRANSITIONS["released"]     # klaim rilis tidak ditarik mundur


@pytest.mark.parametrize("frm,to", [(f, t) for f in EXPECTED_TRANSITIONS for t in EXPECTED_TRANSITIONS if f != t])
def test_status_transitions_follow_the_table(eng, frm, to):
    pid = product(eng)
    vid = version(eng, pid, pin=False)
    with eng.c.app.state.session_factory() as s:
        s.get(ProductVersion, vid).status = frm
        s.commit()
    r = eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"status": to}, headers=eng.auth)
    assert (r.status_code == 200) == (to in EXPECTED_TRANSITIONS[frm]), (frm, to, r.text)
    if r.status_code != 200:
        assert r.json()["code"] == "invalid_transition"


def test_product_status_follows_its_current_version(eng):
    pid = product(eng)
    assert eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["status"] == "draft"
    v1 = version(eng, pid, "1.0", pin=False)
    set_status(eng, pid, v1, "in_development", "internal_testing", "beta", "released")
    v2 = version(eng, pid, "2.0", pin=False)
    p = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()
    assert (p["status"], p["current_version"]) == ("draft", "2.0")             # versi terbaru yang belum diarsipkan
    set_status(eng, pid, v2, "archived")
    p = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()
    assert (p["status"], p["current_version"]) == ("released", "1.0")


# ================================================================== verifikasi klaim fitur

def test_feature_with_real_engineering_evidence_is_verified(eng):
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid)
    assert f["status"] == "verified" and f["evidence"]["problems"] == []
    assert {t["id"] for t in f["evidence"]["tasks"]} == {eng.dev, eng.qa} and f["evidence"]["version_commit"]


def test_feature_without_evidence_is_unverified_with_reasons(eng):
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid, tasks=[])
    assert f["status"] == "unverified" and "Tidak ada task bukti yang terhubung" in f["evidence"]["problems"]


def test_feature_evidence_must_belong_to_the_products_project(eng):
    other = eng.c.post("/api/projects", json={"name": "Lain"}, headers=eng.auth).json()["id"]
    foreign = mk_task(eng.c, eng.auth, other, title="Task asing", role="analyst", action_type="analysis")
    drain(eng.c)
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid, tasks=[foreign])
    assert f["status"] == "unverified" and any("tidak ada pada proyek produk" in p for p in f["evidence"]["problems"])
    f2 = feature(eng, pid, vid, tasks=["task-ngawur"])
    assert f2["status"] == "unverified"


def test_product_without_project_can_never_have_verified_claims(eng):
    pid = eng.c.post("/api/products", json={"name": "Tanpa proyek"}, headers=eng.auth).json()["id"]
    vid = eng.c.post(f"/api/products/{pid}/versions", json={"version": "1"}, headers=eng.auth).json()["id"]
    f = eng.c.post(f"/api/products/{pid}/versions/{vid}/features", json={"text": "Fitur", "task_ids": [eng.dev]}, headers=eng.auth).json()
    assert f["status"] == "unverified" and "Produk belum terhubung ke proyek Engineering" in f["evidence"]["problems"]


def test_evidence_needs_an_implementation_and_passing_tests(eng):
    pid = product(eng)
    vid = version(eng, pid)
    only_qa = feature(eng, pid, vid, tasks=[eng.qa])
    assert only_qa["status"] == "unverified" and any("implementasi" in p for p in only_qa["evidence"]["problems"])
    only_dev = feature(eng, pid, vid, tasks=[eng.dev])
    assert only_dev["status"] == "verified"                                    # tes milik Developer sendiri sudah lulus


def test_implementation_without_any_passing_test_evidence_is_not_enough(settings, auth):
    """Developer selesai (compile ok) tetapi tidak menulis tes: tidak ada bukti tes yang lulus, jadi klaim tidak boleh verified."""
    c = make_client(settings, [gen(("calc.py", CALC), summary="tanpa tes")])
    pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
    dev = mk_task(c, auth, pid, title="Dev tanpa tes", role="developer", action_type="code_change")
    drain(c)
    d = c.get(f"/api/tasks/{dev}", headers=auth).json()
    assert d["status"] == "completed" and d["verification"]["tests_run"] is False and d["test_runs"] == []
    prod = c.post("/api/products", json={"name": "P", "project_id": pid}, headers=auth).json()["id"]
    vid = c.post(f"/api/products/{prod}/versions", json={"version": "1", "pin_commit": True}, headers=auth).json()["id"]
    f = c.post(f"/api/products/{prod}/versions/{vid}/features", json={"text": "Fitur", "task_ids": [dev]}, headers=auth).json()
    assert f["status"] == "unverified"
    assert f["evidence"]["problems"] == ["Tidak ada bukti tes yang lulus pada task terhubung"]


def test_unfinished_evidence_task_is_a_problem(eng):
    pending = mk_task(eng.c, eng.auth, eng.pid, title="Belum jalan", role="developer", action_type="code_change", depends_on=["tidak-ada"]) \
        if False else eng.c.post("/api/tasks", json={"project_id": eng.pid, "title": "Draft", "role": "developer", "action_type": "code_change"}, headers=eng.auth).json()["id"]
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid, tasks=[eng.dev, pending])
    assert f["status"] == "unverified" and any("belum selesai (draft)" in p for p in f["evidence"]["problems"])


def test_failed_latest_test_run_blocks_verification(settings, auth):
    sb = FakeSandbox(pytest=[pytest_fail()])
    c = make_client(settings, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))] * 3, sb)
    pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
    dev = mk_task(c, auth, pid, title="Dev", role="developer", action_type="code_change")
    drain(c)
    assert c.get(f"/api/tasks/{dev}", headers=auth).json()["status"] == "failed"
    prod = c.post("/api/products", json={"name": "P", "project_id": pid}, headers=auth).json()["id"]
    vid = c.post(f"/api/products/{prod}/versions", json={"version": "1", "pin_commit": True}, headers=auth).json()["id"]
    f = c.post(f"/api/products/{prod}/versions/{vid}/features", json={"text": "Fitur", "task_ids": [dev]}, headers=auth).json()
    assert f["status"] == "unverified" and any("belum selesai (failed)" in p for p in f["evidence"]["problems"])


def test_unpinned_version_cannot_verify_claims(eng):
    pid = product(eng)
    vid = version(eng, pid, pin=False)
    f = feature(eng, pid, vid)
    assert f["status"] == "unverified" and any("belum di-pin" in p for p in f["evidence"]["problems"])
    eng.c.post(f"/api/products/{pid}/versions/{vid}/pin-commit", headers=eng.auth)
    after = eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/reverify", headers=eng.auth).json()
    assert after["status"] == "verified"


def test_evidence_from_code_newer_than_the_pinned_commit_is_rejected(settings, auth):
    c = make_client(settings, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))])
    pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
    root = c.app.state.settings.projects_dir / pid / "workspace" / "source-code"
    git.ensure_repo(root)
    (root / "README.md").write_text("awal", encoding="utf-8")
    git.commit_all(root, "awal")                                               # commit A
    prod = c.post("/api/products", json={"name": "P", "project_id": pid}, headers=auth).json()["id"]
    vid = c.post(f"/api/products/{prod}/versions", json={"version": "1", "pin_commit": True}, headers=auth).json()["id"]
    dev = mk_task(c, auth, pid, title="Dev", role="developer", action_type="code_change")
    drain(c)                                                                   # commit B (lebih baru dari yang di-pin)
    f = c.post(f"/api/products/{prod}/versions/{vid}/features", json={"text": "Fitur", "task_ids": [dev]}, headers=auth).json()
    assert f["status"] == "unverified" and any("bukan bagian dari commit versi" in p for p in f["evidence"]["problems"])
    c.post(f"/api/products/{prod}/versions/{vid}/pin-commit", headers=auth)    # pin ulang ke HEAD (B)
    assert c.post(f"/api/products/{prod}/versions/{vid}/features/{f['id']}/reverify", headers=auth).json()["status"] == "verified"


def test_review_requesting_changes_blocks_verification(eng):
    from app.db.models import CodeReview
    with eng.c.app.state.session_factory() as s:
        s.add(CodeReview(task_id=eng.qa, project_id=eng.pid, reviewed_task_ids=[eng.dev], verdict="changes_requested", summary="x"))
        s.commit()
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid)
    assert f["status"] == "unverified" and any("Review independen terbaru meminta perubahan" in p for p in f["evidence"]["problems"])


def test_attach_evidence_later_verifies_the_claim(eng):
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid, tasks=[])
    assert f["status"] == "unverified"
    r = eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/evidence", json={"task_ids": [eng.dev, eng.qa]}, headers=eng.auth).json()
    assert r["status"] == "verified" and set(r["evidence"]["task_ids"]) == {eng.dev, eng.qa}
    assert eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/evidence", json={"task_ids": []}, headers=eng.auth).status_code == 422


def test_attestation_needs_a_human_and_a_reason_and_is_audited(eng):
    pid = product(eng)
    vid = version(eng, pid)
    f = feature(eng, pid, vid, tasks=[])
    path = f"/api/products/{pid}/versions/{vid}/features/{f['id']}"
    short = eng.c.post(f"{path}/attest", json={"reason": "pendek"}, headers=eng.auth)
    assert short.status_code == 422 and short.json()["code"] == "reason_required"
    r = eng.c.post(f"{path}/attest", json={"reason": "Sudah dicoba langsung oleh CEO pada demo"}, headers=eng.auth).json()
    assert (r["status"], r["attested_by"]) == ("attested", "ceo")
    with eng.c.app.state.session_factory() as s:
        log = s.scalars(select(AuditLog).where(AuditLog.action == "product.feature_attested")).one()
        assert log.actor == "ceo" and "demo" in log.details["reason"]
    for actor in ("manager", "analyst", "system", "marketing", ""):
        with eng.c.app.state.session_factory() as s:
            feat = s.scalars(select(__import__("app.db.models", fromlist=["ProductFeature"]).ProductFeature)).first()
            with pytest.raises(ProductError) as e:
                service.attest(s, feat, actor, "alasan yang cukup panjang")
            assert e.value.code == "agent_cannot_decide"


def test_human_set_states_survive_reverification(eng):
    pid = product(eng)
    vid = version(eng, pid)
    path = f"/api/products/{pid}/versions/{vid}/features"
    a, d, w = feature(eng, pid, vid, "Atestasi", []), feature(eng, pid, vid, "Sengketa"), feature(eng, pid, vid, "Ditarik")
    eng.c.post(f"{path}/{a['id']}/attest", json={"reason": "Dibuktikan lewat demo langsung"}, headers=eng.auth)
    assert eng.c.post(f"{path}/{d['id']}/dispute", json={"reason": "ada laporan bug"}, headers=eng.auth).json()["status"] == "disputed"
    assert eng.c.post(f"{path}/{w['id']}/withdraw", headers=eng.auth).json()["status"] == "withdrawn"
    for f in (a, d, w):
        again = eng.c.post(f"{path}/{f['id']}/reverify", headers=eng.auth).json()
        assert again["status"] == {"Atestasi": "attested", "Sengketa": "disputed", "Ditarik": "withdrawn"}[f["text"]]
    assert eng.c.post(f"{path}/{w['id']}/attest", json={"reason": "mencoba menyatakan yang ditarik"}, headers=eng.auth).status_code == 409
    assert eng.c.post(f"{path}/{a['id']}/evidence", json={"task_ids": [eng.dev]}, headers=eng.auth).status_code == 409


def test_evidence_candidates_list_completed_engineering_tasks(eng):
    pid = product(eng)
    cands = eng.c.get(f"/api/products/{pid}/evidence-candidates", headers=eng.auth).json()
    assert {c["id"] for c in cands} == {eng.dev, eng.qa}
    dev = next(c for c in cands if c["id"] == eng.dev)
    assert dev["commit"] and dev["last_test_status"] == "passed"
    nop = eng.c.post("/api/products", json={"name": "Tanpa proyek"}, headers=eng.auth).json()["id"]
    assert eng.c.get(f"/api/products/{nop}/evidence-candidates", headers=eng.auth).json() == []


# ================================================================== Product Release Gate

def test_beta_gate_passes_only_when_every_required_item_passes(eng):
    pid, vid, _ = ready_beta(eng)
    g = gate(eng, pid, vid)
    assert g["ready"] is True and failed(g) == set() and g["target"] == "beta_only"
    assert {i["key"] for i in g["items"] if not i["required"]} == {"no_pending_claims", "pricing_approved", "materials_reviewed"}


@pytest.mark.parametrize("break_it,expected", [
    (lambda e, p, v, f: set_status_back(e, p, v), "status_matches"),
    (lambda e, p, v, f: e.c.patch(f"/api/products/{p}/versions/{v}", json={"limitations": []}, headers=e.auth), "limitations_documented"),
    (lambda e, p, v, f: e.c.patch(f"/api/products/{p}", json={"target_customers": ""}, headers=e.auth), "target_customers"),
    (lambda e, p, v, f: e.c.post(f"/api/products/{p}/versions/{v}/features/{f['id']}/dispute", headers=e.auth), "features_verified"),
])
def test_each_required_item_blocks_the_beta_gate(eng, break_it, expected):
    pid, vid, f = ready_beta(eng)
    break_it(eng, pid, vid, f)
    g = gate(eng, pid, vid)
    assert g["ready"] is False and expected in failed(g)


def set_status_back(e, pid, vid):
    e.c.patch(f"/api/products/{pid}/versions/{vid}", json={"status": "internal_testing"}, headers=e.auth)


def test_gate_requires_pinned_commit_and_system_verified_tests(eng):
    pid = product(eng)
    vid = version(eng, pid, pin=False)
    f = feature(eng, pid, vid, tasks=[])
    eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/attest", json={"reason": "Pernyataan CEO yang cukup panjang"}, headers=eng.auth)
    eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"limitations_confirmed": True}, headers=eng.auth)
    to_beta(eng, pid, vid)
    g = gate(eng, pid, vid)
    assert {"commit_pinned", "tests_passed"} <= failed(g) and "features_verified" not in failed(g)   # atestasi saja bukan bukti tes


def test_limitations_can_be_explicitly_confirmed_as_none(eng):
    pid, vid, _ = ready_beta(eng)
    eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"limitations": []}, headers=eng.auth)
    assert "limitations_documented" in failed(gate(eng, pid, vid))
    eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"limitations_confirmed": True}, headers=eng.auth)
    assert "limitations_documented" not in failed(gate(eng, pid, vid))
    eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"limitations": ["Satu batasan"]}, headers=eng.auth)
    v = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["versions"][0]
    assert v["limitations_confirmed"] is False                                 # batasan nyata menggantikan pernyataan kosong


def ready_released(e):
    pid, vid, f = ready_beta(e)
    set_status(e, pid, vid, "released")
    e.c.patch(f"/api/products/{pid}", json={"pricing_model": "Gratis untuk pelajar"}, headers=e.auth)
    e.c.post(f"/api/products/{pid}/approve-pricing", headers=e.auth)
    e.c.patch(f"/api/products/{pid}/versions/{vid}", json={"materials_reviewed": True}, headers=e.auth)
    return pid, vid, f


def test_full_release_needs_pricing_materials_and_no_pending_claims(eng):
    pid, vid, f = ready_beta(eng)
    set_status(eng, pid, vid, "released")
    g = gate(eng, pid, vid, "allowed")
    assert failed(g) == {"pricing_approved", "materials_reviewed"}
    eng.c.patch(f"/api/products/{pid}", json={"pricing_model": "Rp50.000 per bulan"}, headers=eng.auth)
    eng.c.post(f"/api/products/{pid}/approve-pricing", headers=eng.auth)
    eng.c.patch(f"/api/products/{pid}/versions/{vid}", json={"materials_reviewed": True}, headers=eng.auth)
    assert gate(eng, pid, vid, "allowed")["ready"] is True
    feature(eng, pid, vid, "Ekspor ke PDF", tasks=[])                           # klaim baru tanpa bukti
    assert failed(gate(eng, pid, vid, "allowed")) == {"no_pending_claims"}
    assert gate(eng, pid, vid, "beta_only")["items"][5]["required"] is False    # untuk beta tidak diwajibkan


def test_changing_the_price_after_approval_voids_the_approval(eng):
    pid, vid, _ = ready_released(eng)
    assert gate(eng, pid, vid, "allowed")["ready"] is True
    eng.c.patch(f"/api/products/{pid}", json={"pricing_model": "Rp500.000 per bulan"}, headers=eng.auth)
    assert "pricing_approved" in failed(gate(eng, pid, vid, "allowed"))
    assert eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["pricing_approved"] is False


def test_pricing_cannot_be_approved_when_empty(eng):
    pid = product(eng)
    r = eng.c.post(f"/api/products/{pid}/approve-pricing", headers=eng.auth)
    assert r.status_code == 409 and r.json()["code"] == "no_pricing"


# ================================================================== izin pemasaran

def test_permission_is_refused_while_the_gate_fails_and_the_refusal_is_recorded(eng):
    pid = product(eng)
    vid = version(eng, pid)
    feature(eng, pid, vid)
    r = grant(eng, pid, vid)
    assert r.status_code == 409 and r.json()["code"] == "gate_failed"
    assert {"status_matches", "limitations_documented"} <= set(r.json()["failed"]) and len(r.json()["items"]) == 10
    assert eff(eng, pid, vid) == "not_allowed"
    checks = eng.c.get(f"/api/products/{pid}/versions/{vid}/release-checks", headers=eng.auth).json()
    assert len(checks) == 1 and checks[0]["ready"] is False and checks[0]["target"] == "beta_only" and "status_matches" in checks[0]["failed"]
    with eng.c.app.state.session_factory() as s:
        assert s.scalars(select(AuditLog).where(AuditLog.action == "product.permission_refused")).one().details["target"] == "beta_only"


def test_ceo_grants_beta_permission_when_the_gate_passes(eng):
    pid, vid, _ = ready_beta(eng)
    r = grant(eng, pid, vid, "beta_only", "boleh dipromosikan sebagai beta")
    assert r.status_code == 200
    assert (r.json()["granted_permission"], r.json()["effective_permission"], r.json()["permission_granted_by"]) == ("beta_only", "beta_only", "ceo")
    with eng.c.app.state.session_factory() as s:
        assert s.scalars(select(ProductReleaseCheck)).one().ready is True
        assert s.scalars(select(AuditLog).where(AuditLog.action == "product.permission_granted")).one().details["permission"] == "beta_only"


def test_beta_permission_does_not_extend_to_full_release(eng):
    pid, vid, _ = ready_beta(eng)
    r = grant(eng, pid, vid, "allowed")
    assert r.status_code == 409 and "status_matches" in r.json()["failed"]


def test_agents_can_never_grant_permission(eng):
    pid, vid, _ = ready_beta(eng)
    for actor in ("manager", "analyst", "system", "marketing", "content_promotion", ""):
        with eng.c.app.state.session_factory() as s:
            p = s.get(__import__("app.db.models", fromlist=["Product"]).Product, pid)
            v = s.get(ProductVersion, vid)
            with pytest.raises(ProductError) as e:
                service.grant_permission(s, p, v, "beta_only", actor, "mencoba")
            assert e.value.code == "agent_cannot_decide"
    assert eff(eng, pid, vid) == "not_allowed"


def test_permission_is_revoked_automatically_when_evidence_changes(eng):
    pid, vid, f = ready_beta(eng)
    assert grant(eng, pid, vid).status_code == 200 and eff(eng, pid, vid) == "beta_only"
    eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/dispute", json={"reason": "bug dilaporkan"}, headers=eng.auth)
    v = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["versions"][0]
    assert v["granted_permission"] == "beta_only" and v["effective_permission"] == "not_allowed"      # tersimpan tetapi tidak berlaku
    assert any("Ada fitur yang boleh dipromosikan" in r for r in v["revoked_reasons"])


def test_permission_is_revoked_when_the_status_changes(eng):
    pid, vid, _ = ready_beta(eng)
    grant(eng, pid, vid)
    set_status(eng, pid, vid, "internal_testing")
    v = eng.c.get(f"/api/products/{pid}", headers=eng.auth).json()["versions"][0]
    assert (v["granted_permission"], v["effective_permission"]) == ("not_allowed", "not_allowed")
    assert "dicabut otomatis" in v["permission_reason"]
    with eng.c.app.state.session_factory() as s:
        assert s.scalars(select(AuditLog).where(AuditLog.action == "product.permission_revoked")).first().actor == "system"


def test_changing_the_price_revokes_full_release_permission(eng):
    pid, vid, _ = ready_released(eng)
    assert grant(eng, pid, vid, "allowed").status_code == 200 and eff(eng, pid, vid) == "allowed"
    eng.c.patch(f"/api/products/{pid}", json={"pricing_model": "Rp1.000.000 per bulan"}, headers=eng.auth)
    assert eff(eng, pid, vid) == "not_allowed"
    eng.c.post(f"/api/products/{pid}/approve-pricing", headers=eng.auth)
    assert eff(eng, pid, vid) == "allowed"                         # disetujui ulang pada harga baru


def test_revoking_is_always_allowed_and_audited(eng):
    pid, vid, _ = ready_beta(eng)
    grant(eng, pid, vid)
    r = grant(eng, pid, vid, "not_allowed", "ditarik sementara")
    assert r.status_code == 200 and r.json()["effective_permission"] == "not_allowed"
    assert eng.c.post(f"/api/products/{pid}/versions/{vid}/marketing-permission", json={"permission": "bebas"}, headers=eng.auth).status_code == 422


def test_deleting_a_product_withdraws_promotion_rights(eng):
    pid, vid, _ = ready_beta(eng)
    grant(eng, pid, vid)
    assert eng.c.delete(f"/api/products/{pid}", headers=eng.auth).status_code == 204
    assert eng.c.get(f"/api/products/{pid}", headers=eng.auth).status_code == 404
    assert eng.c.get("/api/products", headers=eng.auth).json() == []
    with eng.c.app.state.session_factory() as s:
        assert s.get(ProductVersion, vid).marketing_permission == "not_allowed"


# ================================================================== ringkasan resmi untuk Marketing

def brief(e, pid, vid):
    return e.c.get(f"/api/products/{pid}/versions/{vid}/marketing-brief", headers=e.auth).json()


def test_brief_exposes_no_claims_until_cleared_and_labels_unverified_ones(eng):
    pid = product(eng)
    vid = version(eng, pid)
    feature(eng, pid, vid, "Penjumlahan dua angka")
    feature(eng, pid, vid, "Integrasi dengan akuntansi", tasks=[])
    b = brief(eng, pid, vid)
    assert b["usable_for_promotion"] is False and b["claims"] == [] and b["effective_permission"] == "not_allowed"
    assert b["blocked_reasons"] == []                                          # belum pernah diberi izin: tidak ada yang dicabut
    assert [c["text"] for c in b["unverified_claims"]] == ["Integrasi dengan akuntansi"]
    assert b["unverified_claims"][0]["label"].startswith("BELUM TERVERIFIKASI") and b["unverified_claims"][0]["problems"]


def test_brief_for_a_cleared_beta_contains_only_verified_claims(eng):
    pid, vid, _ = ready_beta(eng)
    feature(eng, pid, vid, "Integrasi dengan akuntansi", tasks=[])             # tanpa bukti
    attested = feature(eng, pid, vid, "Mendukung bahasa Indonesia", tasks=[])
    eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{attested['id']}/attest", json={"reason": "Diperiksa langsung oleh CEO"}, headers=eng.auth)
    withdrawn = feature(eng, pid, vid, "Fitur lama")
    eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{withdrawn['id']}/withdraw", headers=eng.auth)
    assert grant(eng, pid, vid).status_code == 200
    b = brief(eng, pid, vid)
    assert b["usable_for_promotion"] is True and b["promotion_label"] == "BETA" and b["version"]["status"] == "beta"
    assert {(c["text"], c["basis"]) for c in b["claims"]} == {("Penjumlahan dua angka", "verified"), ("Mendukung bahasa Indonesia", "attested")}
    assert [u["text"] for u in b["unverified_claims"]] == ["Integrasi dengan akuntansi"]
    assert "Fitur lama" not in str(b) and "beta" in b["required_disclaimers"][0].lower()
    assert b["limitations"] == ["Hanya operasi dasar"] and b["pricing"] is None      # harga belum disetujui


def test_brief_shows_pricing_only_when_approved_and_cleared(eng):
    pid, vid, _ = ready_released(eng)
    assert brief(eng, pid, vid)["pricing"] is None                              # belum diberi izin
    grant(eng, pid, vid, "allowed")
    b = brief(eng, pid, vid)
    assert b["pricing"] == "Gratis untuk pelajar" and b["promotion_label"] == "RILIS" and b["required_disclaimers"] == []


def test_brief_after_revocation_explains_why(eng):
    pid, vid, f = ready_beta(eng)
    grant(eng, pid, vid)
    eng.c.post(f"/api/products/{pid}/versions/{vid}/features/{f['id']}/dispute", headers=eng.auth)
    b = brief(eng, pid, vid)
    assert b["usable_for_promotion"] is False and b["claims"] == [] and b["blocked_reasons"]
    assert [u["status"] for u in b["unverified_claims"]] == ["disputed"]


# ================================================================== linter klaim

def brief_for(**kw):
    base = {"product": {"name": "X"}, "version": {"status": "beta"}, "usable_for_promotion": True, "promotion_label": "BETA",
            "blocked_reasons": [], "unverified_claims": [], "pricing": None, "claims": [], "limitations": []}
    base.update(kw)
    return base


def lint(text, **kw):
    from app.products.claims import check_claims
    r = check_claims(text, brief_for(**kw))
    return r["ok"], {f["type"] for f in r["findings"]}


def test_lint_accepts_honest_beta_copy():
    ok, kinds = lint("Versi beta Kalkulator Pro menjumlahkan dua angka dengan cepat.")
    assert ok and kinds == set()


@pytest.mark.parametrize("text", ["Kalkulator terbaik di Indonesia", "Dijamin tanpa bug", "100% akurat untuk beta", "Paling cepat dan paling aman, versi beta",
                                  "Beta sempurna", "Guaranteed results in beta", "Bebas error, beta", "Hasil terbaiknya untuk beta",
                                  "Kesempurnaan? Sempurnanya beta ini", "Akurasi 100 % pada beta", "Beta: 100% aman!"])
def test_lint_blocks_absolute_claims(text):
    ok, kinds = lint(text)
    assert not ok and "absolute_claim" in kinds


@pytest.mark.parametrize("text", ["Produk beta ini sudah dirilis resmi", "Siap produksi, versi beta", "Aplikasi stabil dan sudah tersedia untuk semua", "Production-ready beta",
                                  "Kami senang mengumumkan peluncuran aplikasi (beta)", "Kami meluncurkan aplikasi baru, beta", "Aplikasi telah hadir untuk beta", "Produk beta diluncurkan hari ini"])
def test_lint_blocks_release_claims_for_non_released_versions(text):
    ok, kinds = lint(text)
    assert not ok and "status_misrepresentation" in kinds
    ok2, kinds2 = lint(text, version={"status": "released"}, promotion_label="RILIS")
    assert "status_misrepresentation" not in kinds2


def test_lint_allows_honest_beta_launch_wording():
    ok, kinds = lint("Peluncuran versi beta Kalkulator Pro: menjumlahkan dua angka. Ini masih beta.")
    assert "status_misrepresentation" not in kinds


def test_lint_requires_beta_to_be_disclosed():
    ok, kinds = lint("Kalkulator Pro menjumlahkan dua angka.")
    assert not ok and "beta_not_disclosed" in kinds
    assert lint("Kalkulator Pro menjumlahkan dua angka.", version={"status": "released"}, promotion_label="RILIS")[0] is True


@pytest.mark.parametrize("text", ["Beta ini hanya Rp50.000 per bulan", "Coba gratis versi beta", "Diskon besar untuk beta", "Harga murah, beta", "Beta mulai $9 sebulan"])
def test_lint_blocks_unapproved_pricing(text):
    ok, kinds = lint(text)
    assert not ok and "unapproved_pricing" in kinds
    assert "unapproved_pricing" not in lint(text, pricing="Rp50.000 per bulan")[1]


def test_lint_blocks_mentions_of_unverified_features():
    unverified = [{"id": "1", "text": "Integrasi dengan sistem akuntansi", "status": "unverified", "problems": []}]
    ok, kinds = lint("Beta ini terhubung dengan integrasi sistem akuntansi Anda", unverified_claims=unverified)
    assert not ok and "unverified_feature" in kinds
    assert lint("Beta ini menjumlahkan dua angka", unverified_claims=unverified)[0] is True      # fitur lain tidak terkait


def test_lint_blocks_everything_when_not_cleared():
    ok, kinds = lint("Beta yang jujur dan sederhana.", usable_for_promotion=False, blocked_reasons=["Status pengembangan harus 'beta'"])
    assert not ok and kinds == {"not_cleared"}


def test_lint_endpoint_uses_the_live_brief(eng):
    pid, vid, _ = ready_beta(eng)
    feature(eng, pid, vid, "Integrasi dengan sistem akuntansi", tasks=[])
    path = f"/api/products/{pid}/versions/{vid}/check-claims"
    before = eng.c.post(path, json={"text": "Versi beta yang menjumlahkan angka."}, headers=eng.auth).json()
    assert before["ok"] is False and {f["type"] for f in before["findings"]} == {"not_cleared"}
    grant(eng, pid, vid)
    good = eng.c.post(path, json={"text": "Versi beta yang menjumlahkan angka."}, headers=eng.auth).json()
    assert good["ok"] is True
    bad = eng.c.post(path, json={"text": "Beta dengan integrasi sistem akuntansi, terbaik di kelasnya!"}, headers=eng.auth).json()
    assert bad["ok"] is False and {f["type"] for f in bad["findings"]} == {"unverified_feature", "absolute_claim"}
    assert eng.c.post(path, json={"text": ""}, headers=eng.auth).status_code == 422
