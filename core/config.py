import os
import litellm
from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# DEV_MODE=true  → Claude Haiku for Copywriter (cheaper, faster iteration)
# DEV_MODE=false → Claude Sonnet for Copywriter (submission-quality writing)
# Hunter / Qualifier / Evaluator use the same models in both modes.
# ---------------------------------------------------------------------------
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

# Retries on transient LLM errors (429 rate limits, 500s, connection drops).
# LiteLLM applies these to every completion call made through it (which is how
# CrewAI routes all its model traffic). Exponential backoff between attempts,
# and the Retry-After header is honored when present.
# Set module-level (not per-LLM via additional_params, which gets forwarded
# into the provider SDK call and rejected as an unknown kwarg).
litellm.num_retries = 3

# temperature=0 across the board: deterministic outputs and fewer decoding
# artifacts (gpt-4o-mini at default temp was appending JSON/f-string residue
# after valid SQL in tool calls, causing sqlite tokenizer errors).
if DEV_MODE:
    # Development: gpt-4o for Hunter/Qualifier (previously 4o-mini — upgraded
    # because mini produced trailing `}}]}.JSONArray[{` garbage on INSERT
    # queries despite strong prompt constraints). Evaluator keeps 4o-mini
    # since it emits structured Pydantic output, which is well within mini's
    # capability and isn't exposed to SQL string composition.
    llm_hunter     = LLM(model="gpt-4.1",     api_key=os.environ["OPENAI_API_KEY"], temperature=0)
    llm_qualifier  = LLM(model="gpt-4o",      api_key=os.environ["OPENAI_API_KEY"], temperature=0)
    llm_copywriter = LLM(model="claude-haiku-4-5-20251001",
                         api_key=os.environ["ANTHROPIC_API_KEY"], temperature=0)
    llm_evaluator  = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"], temperature=0)
else:
    # Production: quality models for submission
    # Hunter             → gpt-4.1 (32k output cap — needs room for 12 profiles + write_query INSERTs + HunterOutput in one turn)
    # Qualifier          → gpt-4o  (accurate scoring, per-profile so no output-token pressure)
    # Copywriter         → Claude (best writing quality per dollar)
    # Evaluator          → gpt-4o-mini (structured scoring, doesn't need heavy model)
    llm_hunter     = LLM(model="gpt-4.1",     api_key=os.environ["OPENAI_API_KEY"], temperature=0)
    llm_qualifier  = LLM(model="gpt-4o",      api_key=os.environ["OPENAI_API_KEY"], temperature=0)
    llm_copywriter = LLM(model="claude-sonnet-4-6",
                         api_key=os.environ["ANTHROPIC_API_KEY"], temperature=0)
    llm_evaluator  = LLM(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"], temperature=0)
