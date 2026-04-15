# tasks.py
# Defines all CrewAI Tasks and wires them to agents.
# Each task has a description (what to do), expected_output (what to return),
# an assigned agent, and optional context (previous task outputs it can read).

import os
from crewai import Task
from models import HunterOutput, QualifierOutput, CopywriterOutput, EvaluatorOutput


def create_tasks(agents: dict) -> list[Task]:
    """
    Build and return the ordered list of tasks for the crew.

    Args:
        agents: dict with keys hunter, qualifier, copywriter, evaluator, reporter
    """

    # ------------------------------------------------------------------
    # Task 1 — Lead Discovery
    # Agent: Hunter
    # Tools: LinkedIn mock MCP (search_linkedin_profiles)
    # ------------------------------------------------------------------
    discovery_task = Task(
        description=(
            "Use the LinkedIn mock MCP tool to fetch all candidate profiles. "
            "For each profile, identify which DataStax signals are present:\n"
            "  Tier 1 (high confidence): skills like 'Apache Cassandra', 'DataStax', "
            "'Astra DB', 'DataStax Enterprise', 'CQL'; experience mentioning DataStax "
            "at a non-DataStax company; DataStax Academy certifications; "
            "known_datastax_client=true in the profile (company is a confirmed DataStax customer).\n"
            "  Tier 2 (moderate): LinkedIn posts with #datastax / #astradb / #cassandra; "
            "mentions of migrating from Cassandra or DataStax.\n"
            "Return a list of profiles, each annotated with the signals found."
        ),
        expected_output=(
            "A HunterOutput object containing a list of DiscoveredProfile entries. "
            "Each profile must have tier1_signals and tier2_signals populated with "
            "specific strings describing what was found. Empty lists if no signals."
        ),
        output_pydantic=HunterOutput,
        agent=agents["hunter"],
    )

    # ------------------------------------------------------------------
    # Task 2 — Lead Qualification
    # Agent: Qualifier
    # Tools: validate_lead, calculate_lead_score, get_company_profile
    # Context: Task 1 output
    # ------------------------------------------------------------------
    qualification_task = Task(
        description=(
            "For each candidate from the discovery task:\n"
            "1. Run validate_lead — if the lead currently works at DataStax, IBM DataStax, "
            "or IBM, mark them as BLOCKED and stop processing.\n"
            "2. Run get_company_profile to enrich context about their employer.\n"
            "3. Run calculate_lead_score to get a deterministic base score and breakdown.\n"
            "4. Apply your own judgment to adjust the score up or down based on signals "
            "strength, company fit, and any pain indicators. Document your reasoning.\n"
            "5. Classify each lead: QUALIFIED (score >= 60), SKIPPED (score < 60), "
            "or BLOCKED (guardrail hit)."
        ),
        expected_output=(
            "A QualifierOutput object with every lead classified. "
            "Each QualifiedLead must have status (QUALIFIED/BLOCKED/SKIPPED), "
            "a score (0-100), and qualification_notes explaining the decision."
        ),
        output_pydantic=QualifierOutput,
        agent=agents["qualifier"],
        context=[discovery_task],
    )

    # ------------------------------------------------------------------
    # Task 3 — Message Generation
    # Agent: Copywriter
    # Tools: search_recent_news
    # Context: Task 2 output
    # ------------------------------------------------------------------
    copywriting_task = Task(
        description=(
            "For each QUALIFIED lead from the qualification task, write two messages:\n"
            "1. LinkedIn invite: max 300 characters. Personal, not templated. "
            "Reference at least one specific signal from the lead's profile. "
            "Do NOT mention ScyllaDB by name — keep it curiosity-driven.\n"
            "2. Follow-up email: 100-200 words. Subject line + body.\n\n"
            "Before writing each message set, follow this order:\n"
            "1. Call get_successful_templates with the lead's industry, seniority, "
            "and message_type to retrieve past high-performing examples. "
            "Use them as tone and structure references — do not copy.\n"
            "2. Call search_recent_news('DataStax IBM') to get current DataStax/IBM news.\n"
            "3. Call search_recent_news('ScyllaDB') to get current ScyllaDB news.\n\n"
            "For each lead, choose the outreach angle that best fits their profile "
            "and what the news is showing. Available angles:\n"
            "  - acquisition_uncertainty: IBM roadmap risk, pricing, post-acquisition disruption\n"
            "  - performance_cost: node reduction, latency, infrastructure savings\n"
            "  - migration_simplicity: CQL/driver/SSTable compatibility, zero rewrite\n"
            "  - vendor_independence: open source, no lock-in, community roadmap\n\n"
            "Record the chosen angle in the 'approach' field of each LeadMessages output."
        ),
        expected_output=(
            "A CopywriterOutput with one LeadMessages entry per qualified lead. "
            "Each entry must include: lead_id, lead_name, linkedin_invite (<300 chars), "
            "email_subject, email_body, and approach (one of the four named angles)."
        ),
        output_pydantic=CopywriterOutput,
        agent=agents["copywriter"],
        context=[qualification_task],
    )

    # ------------------------------------------------------------------
    # Task 4 — Message Evaluation
    # Agent: Evaluator
    # Tools: none (pure LLM reasoning with structured output)
    # Context: Task 3 output
    # ------------------------------------------------------------------
    evaluation_task = Task(
        description=(
            "Evaluate each message produced by the copywriter. Score each message "
            "on four dimensions (0-25 each, total 0-100):\n"
            "  - Personalisation: does it reference specific profile signals?\n"
            "  - Tone: professional, warm, not salesy or spammy?\n"
            "  - Relevance: does it connect DataStax pain to ScyllaDB value?\n"
            "  - Format: LinkedIn invite <= 300 chars? Email 100-200 words?\n\n"
            "If total score < 70, mark as REJECTED and provide specific rewrite notes.\n"
            "If score >= 70, mark as APPROVED."
        ),
        expected_output=(
            "An EvaluatorOutput with one EvaluatedMessage per lead. "
            "Each entry must include scores (0-100) and status (APPROVED/REJECTED) "
            "for both the linkedin_invite and email, plus notes explaining the decision. "
            "Approved message content must be included verbatim."
        ),
        output_pydantic=EvaluatorOutput,
        human_input=os.getenv("HUMAN_REVIEW", "true").lower() == "true",
        agent=agents["evaluator"],
        context=[copywriting_task],
    )

    # ------------------------------------------------------------------
    # Task 5 — Persist and Report
    # Agent: Reporter
    # Tools: SQLite MCP (write_lead, write_message), log_dry_run
    # Context: Tasks 1-4 output
    # ------------------------------------------------------------------
    reporting_task = Task(
        description=(
            "Persist all data and generate the final report:\n"
            "1. For every lead (qualified, skipped, blocked), call write_lead to save "
            "to the SQLite database.\n"
            "2. For every approved message, call write_message to save it.\n"
            "3. Call log_dry_run for each approved message to write what would have "
            "been sent to output/dry_run.log.\n"
            "4. Generate a human-readable summary report including:\n"
            "   - Total discovered / qualified / blocked / skipped counts\n"
            "   - List of qualified leads with their scores\n"
            "   - All approved messages (clearly labelled as DRY RUN)\n"
            "   - Any evaluation rejections and the reason"
        ),
        expected_output=(
            "A structured report string covering the full funnel: discovery → "
            "qualification → messaging → evaluation results. All messages clearly "
            "marked as DRY RUN — not sent."
        ),
        agent=agents["reporter"],
        context=[discovery_task, qualification_task, copywriting_task, evaluation_task],
    )

    return [
        discovery_task,
        qualification_task,
        copywriting_task,
        evaluation_task,
        reporting_task,
    ]
