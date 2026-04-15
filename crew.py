import os
import sys
from crewai import Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from dotenv import load_dotenv
from config import llm_default, llm_hunter

load_dotenv()

# Path to the MCP server entrypoint
_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "servers", "linkedin_mock_server.py")
_PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")


def build_crew() -> tuple[Crew, MCPServerAdapter]:
    """
    Instantiate all agents, build tasks, and return a configured Crew.

    Returns both the Crew and the MCPServerAdapter so the caller can manage
    the server lifecycle with a context manager:

        adapter, crew = build_crew()
        with adapter:
            result = crew.kickoff()
    """
    from agents.hunter import create_hunter_agent
    from agents.qualifier import create_qualifier_agent
    from agents.copywriter import create_copywriter_agent
    from agents.evaluator import create_evaluator_agent
    from agents.reporter import create_reporter_agent

    # -- MCP server for the Hunter agent ------------------------------------
    server_params = StdioServerParameters(
        command=_PYTHON,
        args=[_SERVER_SCRIPT],
        env={**os.environ},        # pass current env so .env vars reach the server
    )
    mcp_adapter = MCPServerAdapter(server_params)

    # -- Agents -------------------------------------------------------------
    agents = {
        "hunter":    create_hunter_agent(llm=llm_hunter, tools=mcp_adapter.tools),
        "qualifier": create_qualifier_agent(llm=llm_default),
        "copywriter": create_copywriter_agent(llm=llm_default),
        "evaluator": create_evaluator_agent(llm=llm_default),
        "reporter":  create_reporter_agent(llm=llm_default),
    }

    from tasks import create_tasks
    tasks = create_tasks(agents)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    return mcp_adapter, crew
