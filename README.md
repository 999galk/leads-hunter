# Leads Hunter — ScyllaDB GTM Pipeline

An end-to-end **GTM automation pipeline** that finds DataStax users on LinkedIn, qualifies them as ScyllaDB prospects, writes personalised outreach messages, evaluates them against quality thresholds, and logs a complete dry run — **no real messages are ever sent**.

**Expected run time:** ~4–5 minutes (~270 s end-to-end for 12 mock profiles through all four agents).

---

## Quickstart

```bash
# 1. Install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit .env to add OPENAI_API_KEY and ANTHROPIC_API_KEY

# 3. Run the UI
.venv/bin/python app.py
# → open http://localhost:7860
```

Alternative headless run: `.venv/bin/python main.py`.

---

## Architecture

Sequential 4-agent CrewAI pipeline with typed inter-agent handoffs via Pydantic (`output_pydantic`).

```
Hunter  →  Qualifier  →  Copywriter  →  Evaluator
```

| Agent | Role | Tools | MCP Server | LLM |
|-------|------|-------|------------|-----|
| GTM Lead Hunter | Discovers DataStax users from mock LinkedIn | `search_linkedin_profiles`, `write_query` | LinkedIn mock (stdio, custom) + SQLite (uvx) | GPT-4.1 |
| GTM Qualifier | Scores leads 0–100, classifies QUALIFIED / SKIPPED / BLOCKED | `validate_lead`, `calculate_lead_score`, `get_company_profile`, `write_query` | SQLite (uvx) | GPT-4o |
| GTM Copywriter | Writes LinkedIn invite + follow-up email per lead | `get_successful_templates` (RAG), `search_recent_news`, `write_query`, `read_query` | SQLite (uvx) | Claude Haiku (dev) / Sonnet (prod) |
| GTM Evaluator | Extracts message features; Python computes scores | `write_query`, `read_query` | SQLite (uvx) | GPT-4o-mini |

**Why CrewAI:** first-class agent personas (essential for the Copywriter's tone), `output_pydantic` enforces typed data contracts between agents out of the box, multi-provider LLM support (OpenAI + Anthropic), and sequential process maps cleanly to this pipeline's linear flow.

**MCP servers:** two adapters are live for the duration of every run — a custom stdio server (`servers/linkedin_mock_server.py`) for lead discovery, and the community `uvx mcp-server-sqlite` for DB persistence. Swapping `_load_profiles()` to hit the Apollo API is a documented 5-line change.

**DB persistence is distributed per-agent via MCP writes**, with a Python safety net in `app.py` that upserts any row/field the agents missed via parameterized queries. Apostrophe-prone text fields (`qualification_notes`, `eval_notes`, message content) are intentionally excluded from MCP writes and handled only by the Python path, because LLM-generated raw SQL breaks on single quotes.

**Mid-run UI progression via task callbacks:** the safety net is split into three UPSERT functions (`_python_db_sync_leads`, `_python_db_sync_messages_content`, `_python_db_sync_messages`) wired to CrewAI `Task.callback` hooks. The Leads tab fills as soon as the Qualifier finishes; the Messages tab fills with drafts as soon as the Copywriter finishes; eval scores arrive after the Evaluator. The end-of-run wrapper still runs as a final safety net — idempotent because the callbacks already wrote the same data.

---

## Scoring — Features In, Numbers Out

The Evaluator agent does **not** produce numeric scores. At `temperature=0`, asking an LLM for scalar ratings collapsed every message to the same round number (all 80, all 85). Instead:

1. The LLM extracts **~40 boolean/list/count features per message** (e.g. `li_mentions_name`, `em_superlatives=['game-changing']`, `li_exclamation_marks=2`).
2. A `@model_validator(mode="after")` on `EvaluatedMessage` deterministically computes the four 0–25 dimensions per channel (`personalisation`, `tone`, `relevance`, `format`) and the 0–100 channel totals in Python.
3. Rule-violation caps are applied: a >300-char LinkedIn invite zeros `linkedin_format` and caps the total at 60; an email missing a concrete ScyllaDB value zeros `email_relevance` and caps its total at 60.
4. Messages below 70 are rejected; the Copywriter + Evaluator re-run up to `_MAX_RETRIES=2` times for rejected/missing messages.
5. `_truncate_linkedin_invites()` in `app.py` mechanically enforces the 300-char hard limit after retries as belt-and-braces.

---

## Self-Improvement Loop

Before writing messages, the **Copywriter retrieves the 3 most similar approved past messages** from ChromaDB (matched by industry + seniority) as few-shot examples. The store grows as responses come in — simulated via the **Self-Improvement** tab.

Only `replied` / `accepted` responses are ingested into ChromaDB. Negative feedback is recorded in SQLite only (for audit, not learning).

**Bootstrapping the store (POC):** on the first run, `init_rag()` seeds ChromaDB from `data/seed_templates.json` (8 mock historical messages spanning different approaches, industries, and seniorities) so the Copywriter has non-empty few-shot context from message #1.

**In production:** seed data would be replaced by a **CRM webhook → `ingest_feedback.py`** flow. When a prospect replies or accepts in Salesforce / HubSpot / LinkedIn Sales Navigator, the webhook writes a row into `message_feedback` and calls `rag.add_message()` to embed the winning message. The same gating rule applies — only `replied` / `accepted` are ingested.

---

## Mock Data

LinkedIn profiles are **Apollo.io-shaped JSON** (`data/mock_profiles.json`). The `recent_posts` field is mock-only — in production it would come from a secondary Proxycurl `/person/posts` call.

Profiles `p001`–`p010` are real DataStax-signal leads. `p011` (Tom Nguyen, TechStart) and `p012` (Kevin Moore, FinanceFlow) are intentionally weak leads — each has one weak tier-2 signal so the Hunter keeps them, but the Qualifier scores them well under 60 → SKIPPED. Their purpose is to populate the Leads tab with unqualified examples for the demo.

---

## Key Design Decisions

| Decision | Why |
|---|---|
| LLM extracts features; Python computes scores | Temp=0 LLMs collapse scalar scores to round numbers — features are observable, math is deterministic |
| Certainty-gated SQL sanitizer (`SanitizedSQLTool`) | LLM-generated SQL occasionally had trailing JSON/f-string residue; a strict 5-criteria retry strips it without masking real SQL bugs |
| Dry-run only | `DRY_RUN=true` in `.env` — never sends real messages. Enforced at MCP server + Qualifier guardrail + output logger |
| DataStax/IBM employee filter in two layers | MCP server (Layer 1b) + Qualifier guardrail (Layer 2) — intentional redundancy |
| Python `_python_db_sync_*` safety net wired to task callbacks | Agents sometimes skip their DB write, and the UI needs to fill progressively. Three split UPSERT functions run mid-run via `Task.callback` hooks — Leads tab populates after Qualifier, Messages tab after Copywriter, eval scores after Evaluator |
| Hardcoded SQL templates in agent prompts | Schema-discovery via `list_tables`/`describe_table` was too slow. Trade-off: prompts must be updated manually if the schema changes |

---

## Challenges Overcome

| Bug | Root cause | Fix |
|-----|-----------|-----|
| Evaluator scoring collapse | LLM at temp=0 produced identical round-number scores across all messages | Split `EvaluatedMessage` into feature fields; `@model_validator` computes totals in Python |
| Retry context gap | Copywriter rewrites had no lead profile data, producing generic messages | Retry task now passes full tier-1/tier-2 signals, rejected message text, char count, and per-channel scores |
| LinkedIn 300-char limit | LLM regularly exceeded the platform hard limit | Mechanical word-boundary truncation after retries; `linkedin_format` dimension restored to 20 so scoring is fair |
| Status case mismatch | Agents inserted UPPERCASE status values; UI queries were lowercase | All queries use `LOWER(status)` / `UPPER(eval_status)` |
| Runtime tab truncated tool args | CrewAI's Rich `Live` display truncates multi-line Args panels | Tools emit `[TOOL_ARGS]` single-line markers at entry; `_parse_line` queues them into a FIFO per tool name |

---

## Beyond the Assignment

Features scoped out of this POC but with foundations already in the codebase:

1. **Human-in-the-loop review** — per-message approval / lead exclusion / search-query editing before anything leaves the dry-run log.
2. **Self-improving lead qualification** — extend the RAG loop to track which tier-1/tier-2 signals actually correlate with replies, then feed back into `calculate_lead_score.py`.
3. **Two-phase outreach** — generate the follow-up email only *after* LinkedIn connection acceptance, triggered by a CRM webhook.
4. **Parallel qualification** — batch `validate_lead` + parallelise `get_company_profile` / `calculate_lead_score` across leads; 50–70% Qualifier wall-time reduction expected.
5. **Keyword management UI** — internal page for the GTM team to add/remove/tag search keywords and preview lead-pool impact before going live.

---

## Repository Layout

```
core/                   Shared pipeline modules (config, crew, tasks, models, rag)
agents/                 Agent definitions (hunter, qualifier, copywriter, evaluator)
tools/                  CrewAI @tool functions + SanitizedSQLTool wrapper
servers/                Custom MCP server for mock LinkedIn
data/                   SQLite DB, ChromaDB store, mock profiles, seed templates
output/                 Dry-run log (gitignored, cleared each run)

app.py                  Gradio UI + pipeline orchestrator (primary entry point)
main.py                 Headless CLI runner
database.py             SQLite schema + migrations
ingest_feedback.py      CRM-webhook stand-in — moves responses from SQLite into ChromaDB
```

---

## Environment

See `.env.example`. Required keys:
- `OPENAI_API_KEY` — Hunter, Qualifier, Evaluator
- `ANTHROPIC_API_KEY` — Copywriter
- `DRY_RUN=true` — keep this on; the pipeline will refuse to send real messages

`DEV_MODE=true` uses smaller, cheaper models where possible. `DEV_MODE=false` switches the Copywriter to Claude Sonnet for submission-quality output.
