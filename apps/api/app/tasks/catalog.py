"""Role agent, jenis tindakan, dan kebijakan risiko (Bagian 4 dan 9.3)."""

ROLES: dict[str, str] = {
    "manager": "coordination",
    "analyst": "engineering", "developer": "engineering", "qa": "engineering",
    "reviewer": "engineering", "reporter": "engineering",
    "market_research": "marketing", "lead_generation": "marketing",
    "content_promotion": "marketing", "sales_client_relations": "marketing",
    "seo_specialist": "marketing", "marketing_analytics": "marketing",   # peran on-demand (Phase 14)
}
PLANNABLE_ROLES = [r for r in ROLES if r != "manager"]

# Tingkat risiko ditentukan aturan deterministik berdasarkan jenis tindakan, bukan oleh penilaian model.
ACTION_RISK: dict[str, str] = {
    "planning": "low", "analysis": "low", "documentation": "low", "review": "low", "report": "low",
    # Marketing (Bagian 5.4): riset dan draf bersifat internal; menambah prospek dari sumber yang diizinkan otomatis dengan
    # kontrol privasi (risiko sedang, dicatat). Pengiriman keluar tetap `external_outreach` (kritis, perlu approval).
    "seo_audit": "low", "keyword_research": "low", "content_brief": "low", "marketing_analysis": "low",   # artefak internal, tidak keluar
    "market_research": "low", "lead_intake": "medium", "draft_outreach": "low", "draft_content": "low",
    "code_change": "medium", "run_tests": "medium",
    "install_dependency": "high", "delete_data": "high", "security_config": "high", "network_access": "high",
    "external_outreach": "critical", "publish": "critical", "paid_api": "critical",
    "spend": "critical", "change_pricing": "critical", "use_credentials": "critical",
}
ACTIONS = list(ACTION_RISK)


def risk_for(action_type: str) -> str:
    return ACTION_RISK[action_type]


def needs_approval(risk_level: str) -> bool:
    return risk_level in {"high", "critical"}
