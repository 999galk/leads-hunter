"""
log_dry_run tool
Appends a dry-run record to output/dry_run.log.
Called by the Reporter for every approved message.
Never sends anything — documents what would have been sent.
"""

import os
from datetime import datetime
from crewai.tools import tool

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
_LOG_PATH   = os.path.join(_OUTPUT_DIR, "dry_run.log")


@tool("log_dry_run")
def log_dry_run(lead_name: str, message_type: str, content: str) -> str:
    """
    Write a dry-run record to output/dry_run.log.
    Call this for every approved message before generating the final report.

    Args:
        lead_name:    Full name of the lead (for the log header).
        message_type: 'linkedin_invite' or 'followup_email'.
        content:      Full message text (subject + body for emails).

    Returns:
        Confirmation string with the log file path.
    """
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 72

    entry = (
        f"\n{separator}\n"
        f"[DRY RUN]  {timestamp}\n"
        f"Lead:      {lead_name}\n"
        f"Type:      {message_type}\n"
        f"{separator}\n"
        f"{content}\n"
    )

    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    return f"Logged to {_LOG_PATH}"
