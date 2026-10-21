"""Aturan akses data pemasaran per pelaku (Bagian 4.6). Apa pun yang tidak tercantum DITOLAK.

`ceo` adalah manusia pemegang token lokal. Role agent hanya mendapat izin yang dibutuhkan pekerjaannya:
Market Research tidak pernah melihat data pribadi prospek, dan hanya Sales yang dapat membaca kontak lengkap (tercatat di audit).
"""

HUMAN = {"ceo"}

PERMISSIONS: dict[str, frozenset[str]] = {
    "lead_generation": frozenset({"company.read", "company.write", "lead.create", "lead.read_masked", "lead.update_enrichment",
                                  "source.create", "suppression.check"}),
    "sales_client_relations": frozenset({"company.read", "lead.read_masked", "lead.read_pii", "outreach.draft", "opportunity.read",
                                         "requirement.write", "suppression.check", "product_brief.read"}),
    "market_research": frozenset({"company.read", "product_brief.read", "research.write"}),
    "content_promotion": frozenset({"product_brief.read"}),
    "manager": frozenset({"company.read", "lead.read_masked", "opportunity.read"}),
}


class AccessDenied(PermissionError):
    def __init__(self, actor: str, permission: str):
        super().__init__(f"'{actor}' tidak berwenang untuk '{permission}'")
        self.actor, self.permission = actor, permission


def allowed(actor: str, permission: str) -> bool:
    if actor in HUMAN:
        return True
    return permission in PERMISSIONS.get(actor, frozenset())


def require(actor: str, permission: str) -> None:
    if not allowed(actor, permission):
        raise AccessDenied(actor, permission)


def is_human(actor: str) -> bool:
    return actor in HUMAN
