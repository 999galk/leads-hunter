from crewai.tools import tool

# Mock company intelligence — what you'd get from Apollo org enrichment,
# Clearbit, or internal CRM data in production.
_COMPANY_DB = {
    "netflix": {
        "known_datastax_user": True,
        "scale_notes": "Runs Cassandra at massive scale for personalisation and streaming data.",
        "competitive_notes": "Engineering team well-known for evaluating infra costs aggressively.",
        "scylladb_fit": "High — latency-sensitive, high-throughput workloads.",
    },
    "stripe": {
        "known_datastax_user": True,
        "scale_notes": "Uses DataStax Enterprise for payments ledger — extreme reliability requirements.",
        "competitive_notes": "Fintech regulatory pressure makes vendor stability critical post-IBM acquisition.",
        "scylladb_fit": "High — strong compliance and performance requirements align with ScyllaDB's pitch.",
    },
    "riot games": {
        "known_datastax_user": True,
        "scale_notes": "Player state and matchmaking on Astra DB across multiple regions.",
        "competitive_notes": "Gaming infra teams prioritise low latency above all else.",
        "scylladb_fit": "Very high — sub-millisecond latency is a core ScyllaDB strength.",
    },
    "booking.com": {
        "known_datastax_user": True,
        "scale_notes": "Large-scale availability and pricing data on Cassandra.",
        "competitive_notes": "Large engineering org with dedicated infra team.",
        "scylladb_fit": "Medium-high — scale fits, but large org means longer eval cycles.",
    },
    "spotify": {
        "known_datastax_user": True,
        "scale_notes": "Cassandra-backed event store and vector search on Astra DB.",
        "competitive_notes": "Publicly expressed cost concerns with current Cassandra cluster.",
        "scylladb_fit": "Very high — active cost pain + scale makes them a hot prospect.",
    },
    "capital one": {
        "known_datastax_user": True,
        "scale_notes": "Fraud detection pipeline on DataStax Enterprise, 2M tx/day.",
        "competitive_notes": "Banking regulation adds scrutiny to vendor changes, but IBM acquisition increases risk.",
        "scylladb_fit": "High — performance and reliability requirements match ScyllaDB's strengths.",
    },
    "walmart labs": {
        "known_datastax_user": True,
        "scale_notes": "Cassandra clusters in retail data infrastructure.",
        "competitive_notes": "Publicly mid-migration away from DataStax Enterprise post-IBM acquisition.",
        "scylladb_fit": "Very high — actively looking for alternatives right now.",
    },
    "doordash": {
        "known_datastax_user": True,
        "scale_notes": "Real-time order routing on DataStax.",
        "competitive_notes": "Director-level concern about long-term vendor strategy post-IBM acquisition.",
        "scylladb_fit": "High — real-time logistics is a strong ScyllaDB use case.",
    },
}


@tool("Get Company Profile")
def get_company_profile(company_name: str) -> dict:
    """
    Returns enriched intelligence about a lead's employer — known DataStax
    usage, scale context, and ScyllaDB fit assessment.

    Used by the Qualifier to add business context on top of the signal-based
    score from calculate_lead_score.

    Args:
        company_name: The lead's current employer (e.g. "Netflix", "Stripe").

    Returns:
        dict with: known_datastax_user, scale_notes, competitive_notes, scylladb_fit.
        Returns generic defaults for unknown companies.
    """
    profile = _COMPANY_DB.get(company_name.lower().strip())

    if profile:
        return profile

    # Unknown company — return neutral defaults
    return {
        "known_datastax_user": False,
        "scale_notes": "No specific intelligence available for this company.",
        "competitive_notes": "Unknown company — evaluate based on profile signals alone.",
        "scylladb_fit": "Unknown — assess from industry and seniority signals.",
    }
