"""
Sanitize hallucinated SQL from small-LLM tool calls before retrying.

Small models (gpt-4o-mini in particular) occasionally append decoding residue
after valid SQL — observed: `}}]}.JSONArray[{`, trailing f-string/JSON fragments,
or partial Markdown fences. sqlite then rejects the tokens with
`unrecognized token: "}"` or similar syntax errors.

We sit between the CrewAI agent and the external `uvx mcp-server-sqlite` tool.
On a tokenizer/syntax error, we attempt exactly one retry with a sanitized
prefix — but ONLY when all five certainty criteria pass. If any criterion
fails, we return the original error untouched so a real SQL bug is never masked.
"""

import sqlite3
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

_TOKENIZER_ERROR_MARKERS = ('unrecognized token', 'syntax error', 'near "')
_HALLUCINATION_MARKERS = ("{", "}", "JSONArray", "json.dumps", "f'", 'f"', "```")


def is_tokenizer_error(result: Any) -> bool:
    """True iff result is a sqlite tokenizer/syntax error string."""
    if not isinstance(result, str):
        return False
    lower = result.lower()
    if "database error" not in lower:
        return False
    return any(m in lower for m in _TOKENIZER_ERROR_MARKERS)


def find_clean_prefix(query: str) -> str | None:
    """
    Return a sanitized prefix iff ALL five certainty criteria hold, else None.

      1. Original query contains a hallucination marker.
      2. The query has at least one top-level ';' or balanced ')' split point.
      3. The removed suffix itself contains a hallucination marker.
      4. The prefix is a syntactically complete statement per sqlite3.complete_statement.
      5. The prefix parses under EXPLAIN (syntax-valid; runtime errors like
         no-such-table are tolerated since we're parsing on :memory:).
    """
    if not isinstance(query, str) or not query.strip():
        return None
    if not any(m in query for m in _HALLUCINATION_MARKERS):
        return None  # criterion 1

    split_points = _top_level_split_points(query)
    if not split_points:
        return None  # criterion 2

    for split in reversed(split_points):
        prefix = query[:split].rstrip().rstrip(";") + ";"
        suffix = query[split:].strip()
        if not suffix:
            continue
        if not any(m in suffix for m in _HALLUCINATION_MARKERS):
            continue  # criterion 3
        if not sqlite3.complete_statement(prefix):
            continue  # criterion 4
        if not _prefix_parses(prefix):
            continue  # criterion 5
        return prefix
    return None


def _top_level_split_points(query: str) -> list[int]:
    """Indices (exclusive end) where the query can be split at a top-level ';' or balanced ')'."""
    points: list[int] = []
    depth = 0
    in_string = False
    quote = ""
    i = 0
    while i < len(query):
        c = query[i]
        if in_string:
            if c == quote:
                # SQL escapes quotes by doubling ('' or "")
                if i + 1 < len(query) and query[i + 1] == quote:
                    i += 2
                    continue
                in_string = False
        else:
            if c in ("'", '"'):
                in_string = True
                quote = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    points.append(i + 1)
            elif c == ";" and depth == 0:
                points.append(i + 1)
        i += 1
    return points


def _prefix_parses(sql: str) -> bool:
    """Syntax-check via EXPLAIN on :memory:. Runtime errors (no-such-table) are tolerated."""
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute(f"EXPLAIN {sql}")
        return True
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        # Tables/columns won't exist on :memory: — that's fine, syntax parsed.
        return "no such" in msg
    except sqlite3.Error:
        return False


class SanitizedSQLTool(BaseTool):
    """
    Wrapper around an MCP sqlite tool that retries once with a sanitized query
    when the underlying call returns a tokenizer/syntax error AND all five
    certainty criteria in find_clean_prefix() pass.
    """

    name: str
    description: str
    args_schema: Type[BaseModel] | None = None
    _inner: Any = PrivateAttr()

    def __init__(self, inner_tool: BaseTool):
        super().__init__(
            name=inner_tool.name,
            description=inner_tool.description,
            args_schema=getattr(inner_tool, "args_schema", None),
        )
        self._inner = inner_tool

    def _run(self, **kwargs) -> Any:
        result = self._inner._run(**kwargs)
        query = kwargs.get("query")
        if not query or not is_tokenizer_error(result):
            return result
        clean = find_clean_prefix(query)
        if clean is None or clean == query:
            return result
        return self._inner._run(query=clean)


def wrap_sqlite_tools(tools: list) -> list:
    """Return a list of SanitizedSQLTool wrappers around the given MCP tools."""
    return [SanitizedSQLTool(t) for t in tools]
