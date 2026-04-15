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

Steps pending:
- Step 4: Hunter agent
- Step 5: Qualifier agent + guardrails + tools (validate_lead, calculate_lead_score, get_company_profile)
- Step 6: Copywriter agent + search_recent_news tool
- Step 7: RAG setup — ChromaDB, get_successful_templates tool, seed data, message_feedback DB table
- Step 8: Evaluator agent + HUMAN_REVIEW toggle
- Step 9: Reporter agent + SQLite MCP + dry run log
- Step 10: ingest_feedback.py (closes self-improvement loop)
- Step 11: main.py end-to-end run
- Step 12: Gradio UI (app.py)

## Key architectural decisions

**Framework:** CrewAI with sequential process. 5 agents: Hunter → Qualifier → Copywriter → Evaluator → Reporter. Tasks defined in `tasks.py`, agents in `agents/`.

**LLM split (DEV_MODE=true in .env):**
- Hunter: Groq llama-3.3-70b (fast, near-free — sufficient for filtering)
- All others: gpt-4o-mini
- Before submission flip DEV_MODE=false → Hunter + Qualifier upgrade to gpt-4o, Copywriter upgrades to claude-sonnet-4-6

**Profile data source:** Mock data shaped after Apollo.io's People Search API response format. `_load_profiles()` in `servers/linkedin_mock_server.py` has a comment showing the exact 5-line swap to go live with a real Apollo API key. No provider abstraction — single implementation, extensibility explained in README.

**`recent_posts` field:** Mock-only extension. Apollo doesn't provide post history. In production this would come from a secondary Proxycurl `/person/posts` call on candidates that passed the coarse keyword filter. This is documented in the server file.

**Two-layer filtering:**
- Layer 1 (MCP server): coarse keyword match across technologies, experience, posts, certifications. Runs before the Hunter agent sees any data.
- Layer 2 (Hunter agent): fine-grained signal identification — which signals, Tier 1 vs Tier 2, strength.

**Folder naming:** MCP servers live in `servers/` (not `mcp/`) because `mcp/` would shadow the installed `mcp` Python package.

**Guardrail (hard block):** Any lead whose current employer is DataStax, IBM DataStax, or IBM is blocked before scoring. This runs in the Qualifier agent via the `validate_lead` tool.

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

These are decisions and improvements the user drove — not default choices, but deliberate shaping of the project logic.

**Targeting logic**
- Explicitly defined the target as DataStax *users*, not employees — and stressed this constraint hard. Led to the hard-block guardrail in the Qualifier being a first-class design element, not an afterthought.
- Drove the signal tier system (Tier 1 / Tier 2) and which signals belong where. Pushed to exclude Tier 3 (GitHub, Stack Overflow) as overkill for a POC.
- Asked why not connect to LinkedIn via MCP directly — the answer shaped the clear explanation of what's technically possible (no public API), which will be valuable in the README and verbally.

**Data & schema**
- Pushed back on having separate `leads` and `qualified_leads` tables → merged into one `leads` table with a `status` column. Simpler and correct for POC scope.
- Asked whether the pipeline supports any incoming profile format → led to the Apollo-shaped mock data decision and the `_load_profiles()` swap comment. User will verbally explain provider extensibility.
- Asked about Proxycurl vs Apollo for post data → led to the honest documentation that `recent_posts` is a mock-only extension, and that production would use a secondary Proxycurl enrichment step.

**Tools & agents**
- Asked how to add more tool use in a way that makes technical sense → shaped the tool design philosophy: tools do what LLMs are bad at (deterministic scoring, I/O, external data). Specifically drove the hybrid scoring design: `calculate_lead_score` returns a structured base score, LLM adjusts with reasoning.
- Clarified that `search_recent_news` should run on both DataStax/IBM *and* ScyllaDB — pain signals + value signals — not just one side.
- Clarified that `get_company_profile` is about the *lead's* employer, not DataStax.
- Asked what the `query` parameter in `search_linkedin_profiles` should contain and how to avoid dumping irrelevant profiles on the Hunter → led to the two-layer filtering design being formalised and documented.

**Model strategy**
- Chose CrewAI over OpenAI Agents SDK and Anthropic SDK after discussion.
- Pushed back on using Groq for the Hunter ("isn't discovery one of the most important steps?") → led to the DEV_MODE flag: cheap models during development, quality models (gpt-4o + Claude) before submission.

**Features added**
- **Self-improving Copywriter (RAG):** User's idea. Track response rates, store high-performing messages in ChromaDB, retrieve as few-shot examples for future runs. Closes the feedback loop and demonstrates the pipeline learns from real-world data.
- **Human-in-the-loop:** User's idea. HUMAN_REVIEW flag that pauses execution after evaluation and requires approval before anything is logged as "to be sent". Demonstrates sensitivity awareness and operational confidence-building.
- **Gradio UI:** User's idea. Designed to serve whoever reviews the project — not just a script runner but a full demonstration of the flow and process.

**Simplification calls**
- Killed the multi-provider abstraction (BaseProvider / MockProvider / ApolloProvider / ProxycurlProvider) after it was built — correctly identified it as overkill for a POC. Single implementation with a clear swap comment is the right call. Extensibility explained verbally and in README.

## Important constraints
- Always dry run — `DRY_RUN=true` in `.env`, never send real messages
- Never target DataStax or IBM DataStax employees — hard guardrail in Qualifier
- Keep Anthropic usage minimal during development (limited tokens) — flip DEV_MODE=false only for final submission run
