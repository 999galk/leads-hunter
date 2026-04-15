# main.py
# Entry point. Run with: python main.py
# Always operates in dry-run mode (DRY_RUN=true in .env).
# No real messages are ever sent.

import os
from dotenv import load_dotenv
from rich.console import Console
from crew import build_crew

load_dotenv()
console = Console()


def main():
    console.rule("[bold cyan]Leads Hunter — Dry Run[/bold cyan]")
    console.print(f"[dim]DRY_RUN={os.getenv('DRY_RUN', 'true')}[/dim]\n")

    crew = build_crew()
    result = crew.kickoff()

    console.rule("[bold green]Run Complete[/bold green]")
    console.print(result)


if __name__ == "__main__":
    main()
