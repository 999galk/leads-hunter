from crewai import Agent
from tools.log_dry_run import log_dry_run


def create_reporter_agent(llm, sqlite_tools: list) -> Agent:
    """
    The Reporter is the final agent in the pipeline. It:
      1. Persists every lead via write_query (official mcp-server-sqlite).
      2. Persists every approved message via write_query.
      3. Logs each approved message to output/dry_run.log via log_dry_run.
      4. Generates a human-readable summary of the full pipeline run.

    Args:
        llm:          LLM instance from config.py
        sqlite_tools: Tools from the official mcp-server-sqlite MCP server
                      (read_query, write_query, list_tables, describe_table, ...)
    """
    return Agent(
        role="Pipeline Reporter",
        goal=(
            "Persist all pipeline results to the database using SQL, "
            "log every approved message as a dry run, "
            "and produce a clear summary report of the full funnel."
        ),
        backstory=(
            "You are the final step in the leads pipeline. Your job is methodical: "
            "persist everything, log everything, then summarise.\n\n"

            "You have access to a SQLite database via MCP tools (write_query, read_query, "
            "list_tables, describe_table). Use describe_table to inspect the schema "
            "before writing if needed.\n\n"

            "Database schema:\n"
            "  leads(id, name, title, company, linkedin_url, industry, seniority, "
            "signals, discovery_source, status, score, qualification_notes, created_at)\n"
            "  messages(id, lead_id, type, content, approach, eval_score, "
            "eval_notes, eval_status, retry_count, dry_run, created_at)\n\n"

            "Follow this exact order:\n"
            "1. For EVERY lead (qualified, blocked, and skipped), call write_query "
            "with an INSERT INTO leads statement including industry and seniority. "
            "After inserting, call read_query with SELECT last_insert_rowid() "
            "to get the db_id — you need it for step 2.\n"
            "2. For every APPROVED message, call write_query with an INSERT INTO messages "
            "statement, using the lead's db_id as lead_id. Set dry_run=1 always.\n"
            "3. For every APPROVED message, call log_dry_run.\n"
            "4. Write the summary report.\n\n"

            "The summary report must include:\n"
            "  - Funnel counts: discovered → qualified → blocked → skipped\n"
            "  - Table of qualified leads: name, company, score, approach used\n"
            "  - Each approved message pair (LinkedIn invite + email), "
            "clearly labelled '⚠ DRY RUN — NOT SENT'\n"
            "  - Any rejected messages with their rejection reasons\n"
            "  - Total messages approved vs rejected\n\n"

            "You never skip the persistence steps. Even blocked and skipped leads "
            "must be saved — the full funnel record matters for analysis."
        ),
        tools=[log_dry_run] + sqlite_tools,
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
