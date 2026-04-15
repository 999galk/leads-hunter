# crew.py
# Wires agents and tasks together into a CrewAI Crew.
# Import agents from their modules, create tasks via tasks.py, run the crew.

from crewai import Crew, Process
from dotenv import load_dotenv
from config import llm_default, llm_hunter

load_dotenv()


def build_crew() -> Crew:
    """
    Instantiate all agents, build tasks, and return a configured Crew.
    Process.sequential means tasks run one after another, each passing
    its output as context to the next.
    """
    # Agents — imported and instantiated in their own modules
    # (filled in step 4)
    from agents.hunter import create_hunter_agent
    from agents.qualifier import create_qualifier_agent
    from agents.copywriter import create_copywriter_agent
    from agents.evaluator import create_evaluator_agent
    from agents.reporter import create_reporter_agent

    agents = {
        "hunter": create_hunter_agent(llm=llm_hunter),
        "qualifier": create_qualifier_agent(llm=llm_default),
        "copywriter": create_copywriter_agent(llm=llm_default),
        "evaluator": create_evaluator_agent(llm=llm_default),
        "reporter": create_reporter_agent(llm=llm_default),
    }

    from tasks import create_tasks
    tasks = create_tasks(agents)

    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )
