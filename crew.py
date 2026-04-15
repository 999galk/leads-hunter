import os
import sys
from crewai import Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from dotenv import load_dotenv
from config import llm_hunter, llm_qualifier, llm_copywriter, llm_evaluator, llm_reporter
from rag import init_rag

load_dotenv()

_PYTHON          = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
_LINKEDIN_SERVER = os.path.join(os.path.dirname(__file__), "servers", "linkedin_mock_server.py")
_DB_PATH         = os.path.join(os.path.dirname(__file__), "data", "leads.db")


def build_crew() -> tuple[MCPServerAdapter, MCPServerAdapter, Crew]:
    """
    Instantiate all agents, build tasks, and return both MCP adapters + Crew.

    Callers must manage both adapter lifecycles:

        linkedin_adapter, sqlite_adapter, crew = build_crew()
        with linkedin_adapter, sqlite_adapter:
            result = crew.kickoff()
    """
    init_rag()

    from agents.hunter import create_hunter_agent
    from agents.qualifier import create_qualifier_agent
    from agents.copywriter import create_copywriter_agent
    from agents.evaluator import create_evaluator_agent
    from agents.reporter import create_reporter_agent

    # -- MCP server: LinkedIn mock (Hunter) ---------------------------------
    linkedin_adapter = MCPServerAdapter(StdioServerParameters(
        command=_PYTHON,
        args=[_LINKEDIN_SERVER],
        env={**os.environ},
    ))

    # -- MCP server: SQLite persistence (Reporter) --------------------------
    # Uses the official mcp-server-sqlite package — no custom server needed.
    # Exposes: read_query, write_query, create_table, list_tables, describe_table
    sqlite_adapter = MCPServerAdapter(StdioServerParameters(
        command="uvx",
        args=["mcp-server-sqlite", "--db-path", _DB_PATH],
        env={**os.environ},
    ))

    # -- Agents -------------------------------------------------------------
    agents = {
        "hunter":     create_hunter_agent(llm=llm_hunter, tools=linkedin_adapter.tools),
        "qualifier":  create_qualifier_agent(llm=llm_qualifier),
        "copywriter": create_copywriter_agent(llm=llm_copywriter),
        "evaluator":  create_evaluator_agent(llm=llm_evaluator),
        "reporter":   create_reporter_agent(llm=llm_reporter, sqlite_tools=sqlite_adapter.tools),
    }

    from tasks import create_tasks
    tasks = create_tasks(agents)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    return linkedin_adapter, sqlite_adapter, crew
