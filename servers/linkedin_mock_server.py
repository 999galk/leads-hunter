"""
LinkedIn MCP Server (Apollo mock)
----------------------------------
Serves mock profiles shaped after the Apollo.io People Search API response format.
In production, replace _load_profiles() with a real Apollo API call —
the normalize() function and everything downstream stays unchanged.

Apollo People Search docs:
  https://apolloio.github.io/apollo-api-docs/#people-search
"""

import json
import os
import sys

from mcp.server.fastmcp import FastMCP

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROFILES_PATH = os.path.join(_ROOT, "data", "mock_profiles.json")
_CLIENTS_PATH  = os.path.join(_ROOT, "data", "known_datastax_clients.json")


def _load_known_clients() -> set[str]:
    """Load the curated DataStax client company list as a lowercase set for O(1) lookup."""
    with open(_CLIENTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {name.lower().strip() for name in data.get("companies", [])}


_KNOWN_DATASTAX_CLIENTS = _load_known_clients()

# Apollo seniority strings → canonical tiers
_SENIORITY_MAP = {
    "c_suite":  "executive",
    "vp":       "executive",
    "director": "executive",
    "manager":  "senior",
    "senior":   "senior",
    "mid":      "mid",
    "entry":    "junior",
    "intern":   "junior",
}

_DEFAULT_KEYWORDS = [
    "cassandra", "apache cassandra",
    "datastax", "datastax enterprise", "dse",
    "astra db", "astradb",
    "cql",
]

mcp = FastMCP("linkedin-server")


# ---------------------------------------------------------------------------
# Normalization — Apollo field names → canonical shape
# ---------------------------------------------------------------------------

def normalize(raw: dict) -> dict:
    """Map a single Apollo-shaped profile to the canonical shape the pipeline uses."""
    org = raw.get("organization") or {}

    name = (
        raw.get("name")
        or f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip()
        or "Unknown"
    )

    # Technologies come as a flat list in Apollo
    technologies = raw.get("technologies") or []

    # Employment history: list of dicts with company_name, title, description
    raw_experience = [
        entry.get("description", "")
        for entry in (raw.get("employment_history") or [])
        if entry.get("description")
    ]

    # Apollo doesn't provide post history — kept as a mock-only extension
    # In production this field would be omitted; signals come from technologies
    # and employment history instead.
    recent_posts = raw.get("recent_posts") or []

    seniority = (
        _SENIORITY_MAP.get((raw.get("seniority") or "").lower())
        or _derive_seniority(raw.get("title") or "")
    )

    company_name = raw.get("organization_name") or org.get("name") or "Unknown"

    # True when the company is a known DataStax client from curated case studies.
    # In production this field comes from Apollo's 'technologies_used' filter instead
    # of this static lookup — no code change needed downstream.
    known_client = company_name.lower().strip() in _KNOWN_DATASTAX_CLIENTS

    return {
        "id":                    raw.get("id", ""),
        "name":                  name,
        "title":                 raw.get("title") or "",
        "company":               company_name,
        "linkedin_url":          raw.get("linkedin_url") or "",
        "email":                 raw.get("email") or "",
        "location":              f"{raw.get('city', '')} {raw.get('country', '')}".strip(),
        "seniority":             seniority,
        "industry":              org.get("industry") or "Unknown",
        "company_size":          str(org.get("num_employees") or "Unknown"),
        "technologies":          technologies,
        "raw_experience":        raw_experience,
        "recent_posts":          recent_posts,
        "certifications":        raw.get("certifications") or [],
        "known_datastax_client": known_client,
    }


def _derive_seniority(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["director", "vp ", "vice president", "chief", "head of", "cto", "ceo"]):
        return "executive"
    if any(x in t for x in ["principal", "staff ", "distinguished"]):
        return "principal"
    if any(x in t for x in ["senior", "sr.", "lead", "architect"]):
        return "senior"
    if any(x in t for x in ["junior", "jr.", "associate", "intern"]):
        return "junior"
    return "mid"


# ---------------------------------------------------------------------------
# Coarse pre-filters (Layer 1)
# Layer 2 — fine signal identification — is done by the Hunter agent
# ---------------------------------------------------------------------------

# Employers to exclude at source — no point sending these to the Hunter.
# The Qualifier's validate_lead guardrail is a safety net for edge cases
# (e.g. someone who recently joined DataStax and profile isn't updated yet).
_EXCLUDED_EMPLOYERS = {"datastax", "ibm datastax", "ibm"}


def _is_competitor_employee(profile: dict) -> bool:
    company = (profile.get("company") or "").lower().strip()
    return company in _EXCLUDED_EMPLOYERS


def _keyword_match(profile: dict, keywords: list[str]) -> bool:
    searchable = " ".join([
        " ".join(profile.get("technologies") or []),
        " ".join(profile.get("raw_experience") or []),
        " ".join(profile.get("recent_posts") or []),
        " ".join(profile.get("certifications") or []),
    ]).lower()
    return any(kw.lower() in searchable for kw in keywords)


# ---------------------------------------------------------------------------
# Data loading — swap this for a real Apollo API call in production
# ---------------------------------------------------------------------------

def _load_profiles() -> list[dict]:
    """
    Load profiles from mock JSON file.

    To switch to real Apollo data, replace this function:

        def _load_profiles() -> list[dict]:
            response = requests.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json={"api_key": os.environ["APOLLO_API_KEY"],
                      "q_keywords": ..., "per_page": 25},
            )
            return response.json().get("people", [])

    The normalize() function above handles Apollo's response format as-is.
    """
    with open(_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------

@mcp.tool()
def search_linkedin_profiles(query: str = "") -> str:
    """
    Fetch LinkedIn profiles relevant to the given search query.

    Uses two-layer filtering:
      Layer 1 (here): keyword match across technologies, experience, posts,
                      certifications. Eliminates irrelevant profiles before
                      the Hunter agent sees them.
      Layer 2 (Hunter agent): fine-grained signal identification —
                              which signals, how strong, Tier 1 vs Tier 2.

    Args:
        query: Space or comma-separated keywords to search for.
               e.g. "Apache Cassandra DataStax Astra DB CQL"
               Falls back to default DataStax keyword list if empty.

    Returns:
        JSON string — array of normalized profiles that passed the keyword filter.
    """
    keywords = [k.strip() for k in query.replace(",", " ").split() if k.strip()]
    if not keywords:
        keywords = _DEFAULT_KEYWORDS

    raw_profiles = _load_profiles()
    normalized = [normalize(p) for p in raw_profiles]

    keyword_matched = [p for p in normalized if _keyword_match(p, keywords)]
    filtered = [p for p in keyword_matched if not _is_competitor_employee(p)]

    excluded_count = len(keyword_matched) - len(filtered)

    print(
        f"[linkedin-server] query='{query}'\n"
        f"  {len(raw_profiles)} total"
        f" → {len(keyword_matched)} keyword match"
        f" → {excluded_count} competitor employees removed"
        f" → {len(filtered)} returned to Hunter",
        file=sys.stderr,
    )

    return json.dumps(filtered, indent=2)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
