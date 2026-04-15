"""
get_successful_templates tool
Retrieves top-performing past messages from ChromaDB that match the
current lead's profile. Used by the Copywriter as few-shot examples
before writing new messages.
"""

from crewai.tools import tool
from rag import query_templates


@tool("get_successful_templates")
def get_successful_templates(
    industry: str,
    seniority: str,
    message_type: str,
    approach: str = "",
) -> str:
    """
    Retrieve high-performing past outreach messages for a similar lead profile.
    Call this before writing each message to get few-shot examples.

    Args:
        industry:     Lead's industry (e.g. 'Fintech', 'Gaming', 'Media & Streaming').
        seniority:    Lead's seniority level (e.g. 'senior', 'executive', 'mid').
        message_type: Either 'linkedin_invite' or 'email'.
        approach:     Optional — one of: acquisition_uncertainty, performance_cost,
                      migration_simplicity, vendor_independence. Leave blank to get
                      examples across all approaches.

    Returns:
        Formatted string of example messages that received positive replies.
        Use these as style and tone references — do NOT copy them verbatim.
    """
    examples = query_templates(
        industry=industry,
        seniority=seniority,
        message_type=message_type,
        approach=approach,
    )

    if not examples:
        return "No matching templates found. Write from scratch using your guidelines."

    lines = [
        f"Top {len(examples)} past {message_type.replace('_', ' ')} example(s) "
        f"for {seniority} / {industry} — all received positive replies:\n"
    ]
    for i, ex in enumerate(examples, 1):
        meta = ex["metadata"]
        lines.append(
            f"--- Example {i} "
            f"(approach: {meta.get('approach', 'n/a')}, "
            f"eval score: {meta.get('eval_score', 'n/a')}, "
            f"response: {meta.get('response_type', 'n/a')}) ---"
        )
        lines.append(ex["content"])
        lines.append("")

    lines.append(
        "Use these as reference for tone, structure, and length. "
        "Do NOT copy — the new message must reference this lead's specific signals."
    )
    return "\n".join(lines)
