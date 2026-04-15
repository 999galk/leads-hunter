import os
from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# DEV_MODE=true  → use Groq/gpt-4o-mini across the board (fast, cheap)
# DEV_MODE=false → use production-quality models before submission
# ---------------------------------------------------------------------------
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

if DEV_MODE:
    # Development: speed and cost over quality
    llm_hunter     = LLM(model="groq/llama-3.3-70b-versatile",
                         api_key=os.environ["GROQ_API_KEY"],
                         base_url=os.environ["GROQ_BASE_URL"])
    llm_qualifier  = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
    llm_copywriter = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
    llm_evaluator  = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
    llm_reporter   = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
else:
    # Production: quality models for submission
    # Hunter + Qualifier → gpt-4o (full model, accurate signal detection & scoring)
    # Copywriter         → Claude (best writing quality per dollar)
    # Evaluator          → gpt-4o-mini (structured scoring, doesn't need heavy model)
    # Reporter           → gpt-4o-mini (formatting only)
    llm_hunter     = LLM(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"])
    llm_qualifier  = LLM(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"])
    llm_copywriter = LLM(model="claude-sonnet-4-6",
                         api_key=os.environ["ANTHROPIC_API_KEY"])
    llm_evaluator  = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
    llm_reporter   = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
