import pytest

from app.db.models import ModelCapability, RoutingDecision
from app.providers.base import ModelInfo, ProviderError, ProviderErrorKind as K
from app.routing.router import RoutingError, TaskSnapshot
from app.routing.scoring import category, difficulty_score, normalize_factors
from app.tasks.catalog import ACTION_RISK, ROLES, needs_approval, risk_for
from tests.fakes import FakeProvider
from tests.helpers import build_env, run


def test_difficulty_score_matches_worked_example_in_spec():
    f = {"complexity": 4, "uncertainty": 3, "technical_risk": 2, "scope": 3, "reasoning": 4, "context_requirement": 2}
    assert difficulty_score(f) == 53.75 and category(53.75) == "medium"


def test_difficulty_bounds_and_categories():
    assert difficulty_score({k: 1 for k in normalize_factors(None)}) == 0.0
    assert difficulty_score({k: 5 for k in normalize_factors(None)}) == 100.0
    assert [category(x) for x in (0, 29.99, 30, 59.99, 60, 79.99, 80, 100)] == [
        "light", "light", "medium", "medium", "heavy", "heavy", "critical", "critical"]


def test_normalize_factors_fills_clamps_and_ignores_garbage():
    n = normalize_factors({"complexity": 9, "uncertainty": 0, "scope": "x", "bogus": 5, "reasoning": True})
    assert n["complexity"] == 5 and n["uncertainty"] == 1 and n["scope"] == 3 and n["reasoning"] == 3
    assert "bogus" not in n
    with pytest.raises(ValueError):
        difficulty_score({"complexity": 6})


def test_risk_is_deterministic_by_action_type():
    assert {risk_for(a) for a in ("analysis", "planning", "documentation", "review")} == {"low"}
    assert {risk_for(a) for a in ("code_change", "run_tests")} == {"medium"}
    assert {risk_for(a) for a in ("delete_data", "install_dependency", "security_config", "network_access")} == {"high"}
    assert {risk_for(a) for a in ("external_outreach", "publish", "paid_api", "spend", "change_pricing", "use_credentials")} == {"critical"}
    assert needs_approval("high") and needs_approval("critical") and not needs_approval("medium")
    assert len(ROLES) == 12 and len(ACTION_RISK) == 25  # 1 manager + 5 engineering + 4 marketing + 2 on-demand (Phase 14)


def snap(**kw):
    d = dict(id="t1", project_id="p1", title="T", description="", role="analyst", action_type="analysis",
             acceptance_criteria=[], risk_level="low", requires_approval=False, approved=False,
             difficulty_score=50.0, difficulty_category="medium", preferred_model=None, requires_tools=False, priority=0)
    d.update(kw)
    return TaskSnapshot(**d)


def seed_task(env):
    from tests.helpers import add_task, make_project
    return add_task(env, make_project(env), queue=False)


def choose(env, task_id, **kw):
    s = snap(id=task_id, **kw.pop("snap", {}))
    return run(env.router.choose(s, None, kw.pop("tokens", 500), kw.pop("max_tokens", 256)))


def test_router_picks_model_and_persists_decision(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)
    d = choose(env, tid)
    assert (d.provider, d.model, d.num_ctx) == ("ollama", "fake-model:1b", 4096)
    with env.sf() as s:
        row = s.query(RoutingDecision).one()
        assert row.task_id == tid and row.model == "fake-model:1b" and row.candidates[0]["eligible"] is True
        assert any(r.startswith("difficulty=") for r in row.reasons)


def test_manager_uses_small_models_for_light_and_large_models_for_heavy_tasks(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)
    with env.sf() as s:
        s.query(ModelCapability).filter_by(provider="ollama", model_id="fake-model:1b").update({"available": False})
        s.add_all([
            ModelCapability(provider="ollama", model_id="qwen2.5:3b", available=True, context_limit=8192,
                            supports_tools=True, validation_status="unvalidated", details={"parameter_size": "3.1B"}),
            ModelCapability(provider="ollama", model_id="qwen2.5-coder:7b", available=True, context_limit=8192,
                            supports_tools=True, validation_status="benchmarked", details={"parameter_size": "7.6B"}),
        ])
        s.commit()

    light = choose(env, tid, snap={"difficulty_category": "light", "difficulty_score": 20})
    heavy = choose(env, tid, snap={"difficulty_category": "heavy", "difficulty_score": 70})
    assert light.model == "qwen2.5:3b"
    assert heavy.model == "qwen2.5-coder:7b"


def test_router_grows_context_window_when_needed(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)
    assert choose(env, tid, tokens=4000, max_tokens=1200).num_ctx == 6144
    assert choose(env, tid, tokens=6000, max_tokens=1500).num_ctx == 8192


def test_router_rejects_when_context_exceeds_limit(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)
    with pytest.raises(RoutingError) as e:
        choose(env, tid, tokens=9000, max_tokens=500)
    assert e.value.reason == "no_eligible_model" and "context_exceeded" in e.value.message


def test_router_checks_required_capabilities_without_assuming(migrated_db, tmp_path):
    p = FakeProvider()
    p.models = [ModelInfo("unknown-tools", 8192, None, None), ModelInfo("no-tools", 8192, False, False),
                ModelInfo("with-tools", 8192, True, False)]
    env = build_env(migrated_db, tmp_path, provider=p)
    tid = seed_task(env)
    assert choose(env, tid, snap={"requires_tools": True}).model == "with-tools"
    with env.sf() as s:
        cands = {c["model"]: c["rejected_because"] for c in s.query(RoutingDecision).one().candidates}
    assert cands["unknown-tools"] == ["tools_unknown"] and cands["no-tools"] == ["tools_unsupported"]


def test_router_prefers_explicit_model_then_benchmarked_then_default(migrated_db, tmp_path):
    p = FakeProvider()
    p.models = [ModelInfo("a-model", 8192), ModelInfo("b-model", 8192), ModelInfo("qwen2.5-coder:7b", 8192)]
    env = build_env(migrated_db, tmp_path, provider=p)
    tid = seed_task(env)
    assert choose(env, tid).model == "qwen2.5-coder:7b"                      # default dari konfigurasi
    assert choose(env, tid, snap={"preferred_model": "b-model"}).model == "b-model"
    with env.sf() as s:
        s.query(ModelCapability).filter_by(model_id="a-model").one().validation_status = "benchmarked"
        s.commit()
    assert choose(env, tid).model == "a-model"                               # yang sudah di-benchmark diutamakan


def test_router_prefers_largest_context_for_heavy_tasks(migrated_db, tmp_path):
    p = FakeProvider()
    p.models = [ModelInfo("small", 4096), ModelInfo("big", 32768)]
    env = build_env(migrated_db, tmp_path, provider=p)
    tid = seed_task(env)
    assert choose(env, tid, snap={"difficulty_category": "heavy"}).model == "big"


def test_router_enforces_risk_policy(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)
    with pytest.raises(RoutingError) as e:
        choose(env, tid, snap={"risk_level": "critical", "requires_approval": True})
    assert e.value.reason == "approval_required"
    assert choose(env, tid, snap={"risk_level": "critical", "requires_approval": True, "approved": True})


def test_router_never_selects_paid_provider_when_budget_is_closed(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, ollama_enabled=False)
    tid = seed_task(env)
    from app.providers.registry import build_registry
    env.router._registry = build_registry(env.settings, {"openai": FakeProvider("openai", is_paid=True)})
    with pytest.raises(RoutingError) as e:
        choose(env, tid)
    assert e.value.reason == "no_active_provider"


def test_router_reports_unreachable_provider_as_retryable(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = seed_task(env)

    async def down():
        from app.providers.base import HealthResult
        return HealthResult("down", error_kind="unavailable")
    env.provider.health_check = down
    with pytest.raises(ProviderError) as e:
        choose(env, tid)
    assert e.value.kind == K.unavailable and e.value.retryable
