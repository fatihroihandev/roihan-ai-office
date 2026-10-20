"""Difficulty score 0-100 (Bagian 9.2). Heuristik awal, bukan fakta universal."""

WEIGHTS = {
    "complexity": 0.25, "uncertainty": 0.20, "technical_risk": 0.20,
    "scope": 0.15, "reasoning": 0.15, "context_requirement": 0.05,
}
DEFAULT_FACTORS = {k: 3 for k in WEIGHTS}


def normalize_factors(raw: dict | None) -> dict[str, int]:
    """Lengkapi faktor yang hilang dengan 3 dan jepit nilai ke 1..5."""
    out = dict(DEFAULT_FACTORS)
    for key in WEIGHTS:
        v = (raw or {}).get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = max(1, min(5, int(round(v))))
    return out


def difficulty_score(factors: dict[str, int]) -> float:
    for k, v in factors.items():
        if k not in WEIGHTS or not 1 <= v <= 5:
            raise ValueError(f"Faktor tidak valid: {k}={v}")
    return round(sum(((factors[k] - 1) / 4) * w for k, w in WEIGHTS.items()) * 100, 2)


def category(score: float) -> str:
    if score < 30:
        return "light"
    if score < 60:
        return "medium"
    if score < 80:
        return "heavy"
    return "critical"
