from crewai.tools import tool

# Mirror of the MCP server's exclusion list — kept in sync manually.
# The MCP server filters at source; this is the safety net for edge cases
# (e.g. stale profile data, recent hires, partial employer name matches).
_BLOCKED_EMPLOYERS = {"datastax", "ibm datastax", "ibm"}


@tool("Validate Lead")
def validate_lead(company: str) -> dict:
    """
    Safety-net guardrail: checks whether a lead's current employer is
    DataStax, IBM DataStax, or IBM.

    Must be called FIRST before any scoring. If blocked=True, stop
    processing this lead immediately — do not score or write messages.

    Args:
        company: The lead's current employer name.

    Returns:
        {"blocked": bool, "reason": str}
    """
    normalised = company.lower().strip()

    # Exact match
    if normalised in _BLOCKED_EMPLOYERS:
        return {
            "blocked": True,
            "reason": f"Current employer '{company}' is on the exclusion list. "
                      "We never reach out to DataStax or IBM employees.",
        }

    # Partial match — only on short company names (≤30 chars) to avoid false
    # positives where "datastax" appears in a signal description rather than a
    # real company name (e.g. "Confirmed DataStax Client: Acme Corp").
    if len(normalised) <= 30:
        for blocked in _BLOCKED_EMPLOYERS:
            if blocked in normalised:
                return {
                    "blocked": True,
                    "reason": f"Current employer '{company}' contains a blocked entity "
                              f"('{blocked}'). Flagged as possible DataStax/IBM employee.",
                }

    return {"blocked": False, "reason": ""}
