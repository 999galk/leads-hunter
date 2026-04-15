from crewai.tools import tool

# ---------------------------------------------------------------------------
# Scoring weights — all dimensions sum to 100 at maximum
# ---------------------------------------------------------------------------

# Tier 1: strong, direct evidence of DataStax usage (10 pts each, max 40)
_TIER1_PER_SIGNAL = 10
_TIER1_MAX        = 40

# Tier 2: moderate signals — posts, migration mentions (8 pts each, max 16)
_TIER2_PER_SIGNAL = 8
_TIER2_MAX        = 16

# Seniority: higher = more decision-making power (max 20)
_SENIORITY_SCORES = {
    "executive":  20,
    "principal":  17,
    "senior":     14,
    "mid":        10,
    "junior":      5,
}

# Industry fit: how likely is this industry to benefit from ScyllaDB (max 14)
_INDUSTRY_SCORES = {
    "fintech":              14,
    "fintech / banking":    14,
    "gaming":               13,
    "media & streaming":    13,
    "travel & e-commerce":  11,
    "retail":               10,
    "food delivery / logistics": 10,
    "saas startup":          7,
}
_INDUSTRY_DEFAULT = 8

# Company size: larger = higher scale = more relevant ScyllaDB pitch (max 10)
def _size_score(company_size: str) -> int:
    s = str(company_size).replace(",", "").lower()
    nums = [int(x) for x in s.split() if x.isdigit()]
    n = max(nums) if nums else 0
    if n >= 10000: return 10
    if n >= 5000:  return 8
    if n >= 1000:  return 5
    if n >= 100:   return 3
    return 1


@tool("Calculate Lead Score")
def calculate_lead_score(
    tier1_signals: list,
    tier2_signals: list,
    seniority: str,
    industry: str,
    company_size: str,
) -> dict:
    """
    Deterministic base scoring for a lead. Returns a structured breakdown
    so the Qualifier LLM can see exactly how the score was computed and
    apply its own judgment on top (adjusting up or down with reasoning).

    Scoring dimensions (total max = 100):
      - Tier 1 signals: 10 pts each, capped at 40
      - Tier 2 signals: 8 pts each, capped at 16
      - Seniority:      up to 20 pts
      - Industry fit:   up to 14 pts
      - Company size:   up to 10 pts

    Args:
        tier1_signals: High-confidence DataStax signals from Hunter output.
        tier2_signals: Moderate signals (posts, migration mentions) from Hunter output.
        seniority:     Lead's seniority tier (executive/principal/senior/mid/junior).
        industry:      Lead's employer industry.
        company_size:  Lead's employer headcount string (e.g. "10,000+", "5000").

    Returns:
        {"base_score": int, "breakdown": dict, "notes": str}
    """
    t1 = min(len(tier1_signals) * _TIER1_PER_SIGNAL, _TIER1_MAX)
    t2 = min(len(tier2_signals) * _TIER2_PER_SIGNAL, _TIER2_MAX)
    seniority_score = _SENIORITY_SCORES.get(seniority.lower(), _SENIORITY_SCORES["mid"])
    industry_score  = _INDUSTRY_SCORES.get(industry.lower(), _INDUSTRY_DEFAULT)
    size_score      = _size_score(company_size)

    base = t1 + t2 + seniority_score + industry_score + size_score

    return {
        "base_score": base,
        "breakdown": {
            "tier1_signals": f"{t1}/40  ({len(tier1_signals)} signals × {_TIER1_PER_SIGNAL} pts)",
            "tier2_signals": f"{t2}/16  ({len(tier2_signals)} signals × {_TIER2_PER_SIGNAL} pts)",
            "seniority":     f"{seniority_score}/20  ({seniority})",
            "industry":      f"{industry_score}/14  ({industry})",
            "company_size":  f"{size_score}/10  ({company_size})",
        },
        "notes": (
            "This is the deterministic base score. "
            "Adjust up if there are strong pain signals (e.g. active migration post, "
            "explicit IBM acquisition concern). "
            "Adjust down if signals are weak or context is unclear."
        ),
    }
