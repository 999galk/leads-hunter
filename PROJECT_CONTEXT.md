# Project Context

## What this is
A GTM automation POC built as a home assignment for a ScyllaDB GTM Engineer role.
The pipeline finds DataStax users on LinkedIn, qualifies them, generates personalised outreach messages, evaluates them, and logs everything as a dry run. No real messages are ever sent.

## Business context
- **Target:** DataStax *users* (engineers, architects, leads at companies using DataStax/Cassandra) — never DataStax or IBM DataStax employees
- **Angle:** IBM acquired DataStax in May 2025. This is the primary pain signal — users are re-evaluating vendor lock-in and roadmap risk. ScyllaDB is a drop-in Cassandra replacement, 10x fewer nodes, ~2.5x cheaper.
- **ScyllaDB pitch:** Performance + cost. Same CQL interface, same drivers, same SSTable format. Zero migration friction.

## Build status
Steps completed:
- ✅ Step 1: Project scaffolding (folder structure, config, requirements)
- ✅ Step 2: SQLite schema (`database.py`) + mock profiles (`data/mock_profiles.json`)
- ✅ Step 3: LinkedIn MCP server (`servers/linkedin_mock_server.py`) with Apollo-shaped mock data and two-layer filtering
- ✅ Step 4: Hunter agent (`agents/hunter.py`) + shared Pydantic models (`models.py`) + MCP lifecycle in `crew.py`
- ✅ Step 5: Qualifier agent (`agents/qualifier.py`) + three tools (`tools/validate_lead.py`, `tools/calculate_lead_score.py`, `tools/get_company_profile.py`)

Steps pending:
- Step 6: Copywriter agent + `search_recent_news` tool
- Step 7: RAG setup — ChromaDB, `get_successful_templates` tool, seed data, `message_feedback` DB table
- Step 8: Evaluator agent + `HUMAN_REVIEW` toggle
- Step 9: Reporter agent + SQLite MCP + dry run log
- Step 10: `ingest_feedback.py` (closes self-improvement loop)
- Step 11: `main.py` end-to-end run
- Step 12: Gradio UI (`app.py`)

## Key architectural decisions

**Framework:** CrewAI with sequential process. 5 agents: Hunter → Qualifier → Copywriter → Evaluator → Reporter. Tasks defined in `tasks.py`, agents in `agents/`. Shared Pydantic output models in `models.py` — each task's `output_pydantic` enforces typed data between agents.

**LLM split (DEV_MODE=true in .env):**
- Hunter: Groq llama-3.3-70b (fast, near-free — sufficient for filtering)
- All others: gpt-4o-mini
- Before submission flip DEV_MODE=false → Hunter + Qualifier upgrade to gpt-4o, Copywriter upgrades to claude-sonnet-4-6

**Profile data source:** Mock data shaped after Apollo.io's People Search API response format. `_load_profiles()` in `servers/linkedin_mock_server.py` has a comment showing the exact 5-line swap to go live with a real Apollo API key. No provider abstraction — single implementation, extensibility explained in README.

**`recent_posts` field:** Mock-only extension. Apollo doesn't provide post history. In production this would come from a secondary Proxycurl `/person/posts` call on candidates that passed the coarse keyword filter. This is documented in the server file.

**Two-layer filtering (MCP server):**
- Layer 1a: keyword match across technologies, experience, posts, certifications
- Layer 1b: employer exclusion — DataStax/IBM DataStax/IBM filtered out at source before Hunter sees anything (`_is_competitor_employee()` in the MCP server)
- Layer 2 (Hunter agent): fine-grained signal identification — which signals, Tier 1 vs Tier 2

**Guardrail (safety net):** `validate_lead` tool in the Qualifier is a second-pass safety net for edge cases (stale profile data, recent hires). Primary filtering already happened at the MCP server. Both layers intentional — defence in depth.

**Scoring hybrid (Qualifier):**
- `calculate_lead_score` tool returns a deterministic base score with a structured breakdown (Tier 1 signals, Tier 2 signals, seniority, industry fit, company size — all explicit, max 100)
- Qualifier LLM sees the breakdown and adjusts with written reasoning
- Threshold: QUALIFIED >= 60, SKIPPED < 60, BLOCKED = guardrail hit
- `get_company_profile` tool returns known DataStax usage + ScyllaDB fit notes per company — feeds LLM adjustment

**MCP server lifecycle:** `crew.py`'s `build_crew()` returns `(mcp_adapter, crew)`. Caller uses `with mcp_adapter:` in `main.py` to keep the subprocess alive for the full crew run. Hunter agent receives tools from the adapter — does not manage lifecycle itself.

**Folder naming:** MCP servers live in `servers/` (not `mcp/`) because `mcp/` would shadow the installed `mcp` Python package.

**Self-improvement loop (Step 7):**
- `message_feedback` table tracks response types (replied/accepted/ignored/rejected) per message
- ChromaDB stores embeddings of high-performing messages with metadata (industry, seniority, response_type)
- `get_successful_templates` tool: Copywriter calls this before writing — retrieves top-performing past messages for similar lead profiles as few-shot examples
- `ingest_feedback.py`: manual script to add response data (simulates CRM/webhook integration)
- For the POC: seed a few mock historical successful messages so the RAG has something to retrieve on first run

**Human-in-the-loop (Step 8):**
- Controlled by `HUMAN_REVIEW=true/false` in `.env`
- When true: CrewAI's native `human_input=True` on the Evaluator task — pauses after scoring, shows messages, waits for human approval/feedback before Reporter runs
- When false: fully automated

**UI (Step 12):** Gradio, single `app.py`. 5 tabs: Pipeline Control (run + live log), Leads (funnel + table), Messages (dry run per lead), Self-Improvement (RAG store + simulate feedback), Report (stats + download).

## Environment
- Python venv: `.venv/` — always use `.venv/bin/python`
- `python` command not available on this machine, use `python3` or `.venv/bin/python`
- All API keys already in `.env` (OpenAI, Groq, Anthropic, DeepSeek, Ollama)

## User contributions & design decisions

**Targeting logic**
- Explicitly defined the target as DataStax *users*, not employees — stressed this constraint hard. Led to the hard-block guardrail being a first-class design element.
- Drove the signal tier system (Tier 1 / Tier 2) and which signals belong where. Pushed to exclude Tier 3 (GitHub, Stack Overflow) as overkill for a POC.
- Asked why not connect to LinkedIn via MCP directly — the answer shapes the README and verbal explanation.
- Noticed DataStax employees were reaching the Hunter unnecessarily → led to adding employer exclusion at the MCP server level (Layer 1b). Guardrail is now explicitly a safety net, not primary filter.

**Data & schema**
- Pushed back on separate `leads` and `qualified_leads` tables → merged into one with a `status` column.
- Asked whether the pipeline supports any incoming profile format → led to Apollo-shaped mock data + `_load_profiles()` swap comment. Extensibility explained verbally/README.
- Asked about Proxycurl vs Apollo for post data → `recent_posts` documented as mock-only extension.

**Tools & agents**
- Drove the hybrid scoring design: deterministic base + LLM adjustment with written reasoning.
- Clarified `search_recent_news` runs on both DataStax/IBM (pain) and ScyllaDB (value).
- Clarified `get_company_profile` is about the lead's employer, not DataStax.
- Asked what the `query` param in `search_linkedin_profiles` should contain → formalised the two-layer filtering design.

**Model strategy**
- Chose CrewAI over OpenAI Agents SDK and Anthropic SDK.
- Pushed back on Groq for Hunter → DEV_MODE flag with cheap dev models / quality prod models.

**Features added**
- Self-improving Copywriter via RAG (ChromaDB + response tracking)
- Human-in-the-loop with on/off toggle
- Gradio UI for project reviewers

**Simplification calls**
- Killed multi-provider abstraction after it was built — overkill for POC.

## Important constraints
- Always dry run — `DRY_RUN=true` in `.env`, never send real messages
- Never target DataStax or IBM DataStax employees — filtered at MCP server + safety net in Qualifier
- Keep Anthropic usage minimal during development — flip DEV_MODE=false only for final submission run
