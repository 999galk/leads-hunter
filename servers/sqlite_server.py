# SQLite MCP Server wrapper
# Lives in servers/ (not mcp/) to avoid shadowing the installed mcp package.
# Wraps the official MCP SQLite server to persist leads and messages.
# Exposes tools: write_lead, write_message, query_leads, query_messages.
# Called by the Reporter agent at the end of the pipeline.
