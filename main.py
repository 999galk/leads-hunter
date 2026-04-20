"""Headless pipeline runner. For the Gradio UI, use `app.py` instead."""

import os
from dotenv import load_dotenv
from rich.console import Console
from database import init_db, clear_run_data
from core.crew import build_crew

load_dotenv()
console = Console()


def main():
    console.rule("[bold cyan]Leads Hunter — Dry Run[/bold cyan]")
    console.print(f"[dim]DRY_RUN={os.getenv('DRY_RUN', 'true')}  "
                  f"DEV_MODE={os.getenv('DEV_MODE', 'true')}[/dim]\n")

    init_db()
    clear_run_data()

    linkedin_adapter, sqlite_adapter, crew = build_crew()
    with linkedin_adapter, sqlite_adapter:
        result = crew.kickoff()

    console.rule("[bold green]Run Complete[/bold green]")
    console.print(result)


if __name__ == "__main__":
    main()
