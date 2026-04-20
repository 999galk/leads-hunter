"""
ingest_feedback.py
------------------
Closes the self-improvement loop by moving response data from SQLite
into ChromaDB so the Copywriter gets better examples on the next run.

In production this would be triggered by a CRM webhook or LinkedIn
response event. For the POC, run it manually after simulating responses.

Usage:
    python ingest_feedback.py              # process all pending feedback
    python ingest_feedback.py --add        # record a new response interactively
    python ingest_feedback.py --status     # show feedback stats and RAG store size
"""

import argparse
from database import init_db, get_connection
from core.rag import init_rag, add_message, _get_collection

try:
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    _RICH = True
except ImportError:
    _RICH = False

console = Console() if _RICH else None


def _print(msg: str, style: str = "") -> None:
    if console:
        console.print(msg, style=style)
    else:
        print(msg)


# ---------------------------------------------------------------------------
# Process pending feedback
# ---------------------------------------------------------------------------

def process_pending() -> int:
    """
    Read all message_feedback rows where ingested=0, push them into ChromaDB,
    then mark them as ingested. Returns the number of records processed.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                mf.id          AS feedback_id,
                mf.message_id,
                mf.response_type,
                mf.notes,
                m.type         AS message_type,
                m.content,
                m.approach,
                m.eval_score,
                l.industry,
                l.seniority
            FROM message_feedback mf
            JOIN messages m ON m.id = mf.message_id
            JOIN leads    l ON l.id = m.lead_id
            WHERE mf.ingested = 0
        """).fetchall()

    if not rows:
        _print("No pending feedback to process.", style="dim")
        return 0

    ingested = 0
    for row in rows:
        add_message(
            message_id=str(row["message_id"]),
            content=row["content"],
            message_type=row["message_type"],
            approach=row["approach"] or "",
            industry=row["industry"] or "Unknown",
            seniority=row["seniority"] or "Unknown",
            response_type=row["response_type"],
            eval_score=row["eval_score"] or 0,
        )

        with get_connection() as conn:
            conn.execute(
                "UPDATE message_feedback SET ingested=1 WHERE id=?",
                (row["feedback_id"],)
            )

        status = "added to RAG" if row["response_type"] in ("replied", "accepted") else "skipped (negative)"
        _print(f"  message {row['message_id']:>4}  [{row['response_type']:<8}]  {status}")
        ingested += 1

    return ingested


# ---------------------------------------------------------------------------
# Add feedback interactively
# ---------------------------------------------------------------------------

def add_feedback_interactive() -> None:
    """
    Show recent approved messages and let the user record a response type.
    Simulates receiving a CRM/LinkedIn webhook event.
    """
    with get_connection() as conn:
        messages = conn.execute("""
            SELECT m.id, m.type, m.approach, m.eval_score,
                   l.name AS lead_name, l.company
            FROM messages m
            JOIN leads l ON l.id = m.lead_id
            WHERE m.eval_status = 'APPROVED'
            ORDER BY m.created_at DESC
            LIMIT 20
        """).fetchall()

    if not messages:
        _print("No approved messages in the database yet. Run the pipeline first.", style="yellow")
        return

    if _RICH:
        table = Table(title="Recent Approved Messages", show_lines=True)
        table.add_column("ID",       style="cyan",  no_wrap=True)
        table.add_column("Lead",     style="white")
        table.add_column("Company",  style="white")
        table.add_column("Type",     style="green")
        table.add_column("Approach", style="yellow")
        table.add_column("Score",    style="magenta")
        for m in messages:
            table.add_row(
                str(m["id"]), m["lead_name"], m["company"],
                m["type"], m["approach"] or "—", str(m["eval_score"] or "—")
            )
        console.print(table)
    else:
        for m in messages:
            print(f"{m['id']:>3}  {m['lead_name']:<20}  {m['type']:<16}  {m['approach']}")

    msg_id = Prompt.ask("\nEnter message ID to record feedback for") if _RICH \
        else input("\nEnter message ID: ")

    try:
        msg_id = int(msg_id)
    except ValueError:
        _print("Invalid ID.", style="red")
        return

    valid_responses = ["replied", "accepted", "ignored", "rejected"]
    if _RICH:
        response_type = Prompt.ask(
            "Response type",
            choices=valid_responses,
            default="replied"
        )
        notes = Prompt.ask("Notes (optional, press Enter to skip)", default="")
    else:
        response_type = input(f"Response type {valid_responses}: ").strip()
        notes = input("Notes (optional): ").strip()

    if response_type not in valid_responses:
        _print(f"Invalid response type. Must be one of: {valid_responses}", style="red")
        return

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO message_feedback (message_id, response_type, notes) VALUES (?,?,?)",
            (msg_id, response_type, notes or None)
        )

    _print(f"\nFeedback recorded for message {msg_id}: [bold]{response_type}[/bold]", style="green")

    if _RICH:
        ingest_now = Confirm.ask("Ingest into ChromaDB now?", default=True)
    else:
        ingest_now = input("Ingest into ChromaDB now? [y/N]: ").strip().lower() == "y"

    if ingest_now:
        n = process_pending()
        _print(f"{n} record(s) ingested.", style="green")


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------

def show_status() -> None:
    init_rag()
    collection = _get_collection()
    chroma_count = collection.count()

    with get_connection() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM message_feedback").fetchone()[0]
        pending  = conn.execute("SELECT COUNT(*) FROM message_feedback WHERE ingested=0").fetchone()[0]
        by_type  = conn.execute("""
            SELECT response_type, COUNT(*) as n
            FROM message_feedback GROUP BY response_type
        """).fetchall()

    _print("\n[bold]Feedback stats[/bold]")
    _print(f"  Total feedback records : {total}")
    _print(f"  Pending ingestion      : {pending}")
    for row in by_type:
        _print(f"  {row['response_type']:<10} : {row['n']}")
    _print(f"\n[bold]ChromaDB[/bold]")
    _print(f"  Templates in store : {chroma_count}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest message feedback into ChromaDB.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add",    action="store_true", help="Record a new response interactively")
    group.add_argument("--status", action="store_true", help="Show feedback stats and RAG store size")
    args = parser.parse_args()

    init_db()
    init_rag()

    if args.add:
        add_feedback_interactive()
    elif args.status:
        show_status()
    else:
        _print("[bold]Processing pending feedback...[/bold]")
        n = process_pending()
        _print(f"\n[green]{n} record(s) ingested into ChromaDB.[/green]")
