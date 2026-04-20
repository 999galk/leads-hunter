# tasks.py
# Defines all CrewAI Tasks and wires them to agents.
# Each task has a description (what to do), expected_output (what to return),
# an assigned agent, and optional context (previous task outputs it can read).

import os
from crewai import Task
from core.models import HunterOutput, QualifierOutput, CopywriterOutput, EvaluatorOutput


def create_tasks(agents: dict) -> list[Task]:
    sender_name  = os.getenv("SENDER_NAME", "Your Name")
    sender_title = os.getenv("SENDER_TITLE", "Solutions Architect")
    """
    Build and return the ordered list of tasks for the crew.

    Args:
        agents: dict with keys hunter, qualifier, copywriter, evaluator
    """

    # ------------------------------------------------------------------
    # Task 1 — Lead Discovery
    # Agent: Hunter
    # Tools: LinkedIn mock MCP (search_linkedin_profiles), sqlite MCP (write_query)
    # ------------------------------------------------------------------
    discovery_task = Task(
        description=(
            "Call search_linkedin_profiles to fetch candidate profiles. "
            "Use the tool's real data — never invent or substitute names, companies, or URLs.\n\n"
            "Each profile already has pre-computed 'tier1_signals' and 'tier2_signals' lists. "
            "Copy those plus 'name', 'company', 'title', 'seniority', 'industry', "
            "'company_size', 'linkedin_url', 'email', 'id' verbatim into DiscoveredProfile.\n\n"
            "DB PERSISTENCE — for EACH profile, call write_query:\n"
            "  INSERT OR IGNORE INTO leads\n"
            "    (name, title, company, linkedin_url, industry, seniority, signals, discovery_source, status)\n"
            "  VALUES ('<name>', '<title>', '<company>', '<linkedin_url>',\n"
            "          '<industry>', '<seniority>', '<signals_str>', 'linkedin_mock', 'discovered')\n"
            "For <signals_str>: copy the profile's 'signals_str' field as-is — plain comma-separated, "
            "no braces, no JSON, no inner quotes.\n"
            "CRITICAL SQL RULES: (1) Replace any single quote (') in a value with two single quotes (''). "
            "(2) Never use curly braces {{ }} anywhere in the SQL. "
            "(3) Write plain string values only — no Python f-strings, no JSON objects.\n"
        ),
        expected_output=(
            "A HunterOutput whose profiles list mirrors the tool response exactly — "
            "real name/company/URL, no placeholders. tier1_signals and tier2_signals "
            "copied from the profile's pre-computed fields."
        ),
        output_pydantic=HunterOutput,
        agent=agents["hunter"],
    )

    # ------------------------------------------------------------------
    # Task 2 — Lead Qualification
    # Agent: Qualifier
    # Tools: validate_lead, calculate_lead_score, get_company_profile, sqlite MCP
    # Context: Task 1 output
    # ------------------------------------------------------------------
    qualification_task = Task(
        description=(
            "For each candidate from the discovery task:\n"
            "1. Run validate_lead — if they currently work at DataStax, IBM DataStax, or IBM, "
            "mark BLOCKED and stop.\n"
            "2. Run get_company_profile for employer context.\n"
            "3. Run calculate_lead_score for a deterministic base score + breakdown.\n"
            "4. Adjust up or down based on signal strength, company fit, and pain indicators. "
            "Document your reasoning.\n"
            "5. Classify: QUALIFIED (score >= 60), SKIPPED (score < 60), or BLOCKED (guardrail hit).\n\n"
            "DB PERSISTENCE — for each lead call write_query:\n"
            "  UPDATE leads SET status='<status_lower>', score=<score>\n"
            "  WHERE name='<name>' AND company='<company>'\n"
            "Status is lowercase: 'qualified', 'blocked', or 'skipped'. "
            "Do NOT include qualification_notes — only status and score.\n"
            "CRITICAL SQL RULES: (1) Replace any single quote (') in a name/company value with two single quotes (''). "
            "(2) Never use curly braces {{ }} anywhere in the SQL. "
            "(3) <score> must be a plain integer like 75 — no arithmetic expressions, no braces."
        ),
        expected_output=(
            "A QualifierOutput whose 'leads' list contains EVERY candidate from discovery "
            "(QUALIFIED + BLOCKED + SKIPPED — omit none). Each QualifiedLead: status "
            "(QUALIFIED/BLOCKED/SKIPPED), score (0-100), qualification_notes with the reasoning. "
            "The 'qualified'/'blocked'/'skipped' counts must match the list."
        ),
        output_pydantic=QualifierOutput,
        agent=agents["qualifier"],
        context=[discovery_task],
    )

    # ------------------------------------------------------------------
    # Task 3 — Message Generation
    # Agent: Copywriter
    # Tools: search_recent_news, get_successful_templates, sqlite MCP
    # Context: Task 2 output
    # ------------------------------------------------------------------
    copywriting_task = Task(
        description=(
            "Write personalised outreach messages for every QUALIFIED lead.\n\n"
            "STEP 1 — Gather context ONCE (do NOT repeat per lead):\n"
            "  a. Call search_recent_news('DataStax IBM') — read and remember the results.\n"
            "  b. Call search_recent_news('ScyllaDB') — read and remember the results.\n\n"
            "STEP 2 — For EACH qualified lead (process all of them):\n"
            "  a. Call get_successful_templates once for that lead's profile.\n"
            "  b. Write a LinkedIn invite (STRICT rules below).\n"
            "  c. Write a follow-up email: 100-200 words. Subject + body. Weave in "
            "the news context from Step 1. Clearly name ScyllaDB as the alternative "
            "and connect their DataStax/Cassandra experience to the value we offer.\n"
            "  d. Choose the best angle for this lead:\n"
            "     acquisition_uncertainty | performance_cost | "
            "migration_simplicity | vendor_independence\n\n"
            "LINKEDIN INVITE RULES (all must be followed to pass evaluation):\n"
            "  1. Hard limit: 300 characters INCLUDING spaces — count carefully.\n"
            "  2. Mention their specific role or company (personalisation).\n"
            "  3. Reference their Cassandra/DataStax background or a tier-1 signal "
            "     (e.g. their tech stack, certification, or known usage).\n"
            "  4. Hint at a relevant topic — e.g. 'navigating the IBM acquisition' or "
            "     'exploring Cassandra-compatible alternatives' — without naming ScyllaDB.\n"
            "  5. Warm, conversational tone — no buzzwords, no hard sell.\n"
            "  6. End with a soft ask: 'Would love to connect' or 'Happy to share thoughts'.\n\n"
            "  Good example (adjust names/signals to the actual lead):\n"
            "  'Hi [Name], saw your Cassandra background at [Company] — "
            "with the IBM acquisition shaking things up I've been talking to a lot of "
            "engineers exploring options. Would love to connect.'\n"
            "  (That example is 188 chars — stay in the 150-280 char sweet spot.)\n\n"
            "You MUST produce one message set per qualified lead.\n\n"
            f"Sign every email:\n{sender_name}\n{sender_title}, ScyllaDB\n\n"
            "DB PERSISTENCE — for EACH qualified lead after writing messages:\n"
            "  1. INSERT a row for the LinkedIn invite:\n"
            "     INSERT OR IGNORE INTO messages\n"
            "       (lead_id, type, content, approach, dry_run)\n"
            "     VALUES ((SELECT id FROM leads WHERE name='<name>' AND company='<company>'),\n"
            "             'linkedin_invite', 'draft', '<approach>', 1)\n"
            "  2. INSERT a row for the follow-up email:\n"
            "     INSERT OR IGNORE INTO messages\n"
            "       (lead_id, type, content, approach, dry_run)\n"
            "     VALUES ((SELECT id FROM leads WHERE name='<name>' AND company='<company>'),\n"
            "             'followup_email', 'draft', '<approach>', 1)\n"
            "Use literal string 'draft' for content — the Python safety net writes the full text later.\n"
            "CRITICAL SQL RULES: (1) Replace any single quote (') in a name/company value with two single quotes (''). "
            "(2) Never use curly braces {{ }} anywhere in the SQL. "
            "(3) <approach> must be one of the four exact keywords (no braces, no quotes inside).\n"
            "Do NOT call read_query, list_tables, or describe_table — the schema is already "
            "described above."
        ),
        expected_output=(
            "A CopywriterOutput where the 'messages' list contains EXACTLY ONE entry "
            "per qualified lead — no more, no fewer. "
            "Each entry: lead_id, lead_name, linkedin_invite (<300 chars), "
            "email_subject, email_body, approach (one of the four named angles)."
        ),
        output_pydantic=CopywriterOutput,
        agent=agents["copywriter"],
        context=[qualification_task],
    )

    # ------------------------------------------------------------------
    # Task 4 — Message Evaluation
    # Agent: Evaluator
    # Tools: sqlite MCP (write_query, read_query)
    # Context: Task 3 output
    # ------------------------------------------------------------------
    evaluation_task = Task(
        description=(
            "Extract FEATURES from each message set (LinkedIn invite + email). "
            "You are NOT scoring — Python computes scores from your features.\n\n"

            "INPUTS:\n"
            "  • Copywriter output — one LeadMessages per qualified lead\n"
            "  • Qualifier output — each lead's tier1_signals / tier2_signals\n\n"

            "FOR EACH LEAD:\n"
            "  1. Copy lead_id, lead_name, linkedin_invite, email_subject, email_body\n"
            "     VERBATIM from the copywriter output into EvaluatedMessage.\n"
            "  2. Fill every li_* feature by literal observation of the invite text\n"
            "     (follow feature definitions in your backstory).\n"
            "  3. Fill every em_* feature by literal observation of the email body.\n"
            "  4. Cross-reference tier1_signals / tier2_signals against the message text.\n"
            "     Put into li_tier1_refs / em_tier1_refs ONLY signals that literally\n"
            "     appear verbatim in the respective message. Same for tier2_refs.\n"
            "  5. linkedin_notes: one-liner (char count + strongest signal).\n"
            "     email_notes: one-liner (word count + strongest signal).\n\n"

            "DO NOT output linkedin_personalisation / linkedin_tone / linkedin_relevance /\n"
            "linkedin_format / linkedin_score / linkedin_status / linkedin_char_count.\n"
            "DO NOT output email_personalisation / email_tone / email_relevance /\n"
            "email_format / email_score / email_status / email_word_count.\n"
            "Leave them as defaults (0 / APPROVED) — Python fills them from your features.\n\n"

            "Do NOT call any SQL tools — the Python safety net writes evaluator results\n"
            "to the DB. Your only job is to populate the EvaluatedMessage feature fields."
        ),
        expected_output=(
            "An EvaluatorOutput with one EvaluatedMessage per lead. Each must have: "
            "lead_id, lead_name, content fields (linkedin_invite, email_subject, email_body) "
            "copied verbatim, and every li_* / em_* feature field filled by literal "
            "observation. Do NOT fill dimension, _score, _status, or char/word count "
            "fields — Python computes those."
        ),
        output_pydantic=EvaluatorOutput,
        agent=agents["evaluator"],
        context=[qualification_task, copywriting_task],
    )

    return [
        discovery_task,
        qualification_task,
        copywriting_task,
        evaluation_task,
    ]
