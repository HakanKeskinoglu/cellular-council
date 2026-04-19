# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
CCA Command-Line Interface.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cca.core import ConsensusStrategy
from cca.llm.backends import OllamaBackend
from cca.core.council import Council
from cca.cells.specialized import create_cell
from cca.core import CellRole, SignalType

# Optional imports
try:
    from examples.alertmind.alarm_decision import (
        DataCenterAlarm,
        create_alertmind_council,
        process_alarm,
    )
    HAS_ALERTMIND = True
except ImportError:
    HAS_ALERTMIND = False


console = Console()


def configure_logging(verbose: bool) -> None:
    """Configure structured logging based on verbosity."""
    if not verbose:
        # Disable logging for cleaner CLI output unless verbose
        logging.getLogger("cca").setLevel(logging.CRITICAL + 1)
        return

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def main(verbose: bool) -> None:
    """🧬 Cellular Council Architecture (CCA) — CLI"""
    configure_logging(verbose)


@main.command()
@click.option("--model", default="llama3.2", help="Ollama model name")
@click.option(
    "--strategy",
    default="weighted_average",
    type=click.Choice([s.value for s in ConsensusStrategy]),
    help="Consensus strategy.",
)
@click.option("--debate-rounds", default=1, type=int, help="Number of debate rounds.")
@click.argument("query")
def deliberate(model: str, strategy: str, debate_rounds: int, query: str) -> None:
    """Run a basic deliberation on a query."""
    console.print(Panel(f"[bold blue]CCA Deliberation[/bold blue]\nModel: {model} | Strategy: {strategy}"))

    async def _run() -> None:
        backend = OllamaBackend(model=model)
        if not await backend.health_check():
            console.print(f"[bold red]Error:[/bold red] Ollama model '{model}' is not responding.")
            sys.exit(1)

        council = Council(
            name="CLI_Council",
            llm_backend=backend,
            strategy=ConsensusStrategy(strategy),
            debate_rounds=debate_rounds,
        )

        # Add a mix of cells
        council.add_cell(CellRole.TECHNICAL)
        council.add_cell(CellRole.RISK)
        council.add_cell(CellRole.ETHICS)

        with console.status("[bold green]Deliberating... (this may take a while)[/bold green]"):
            decision = await council.deliberate(query)

        console.print("\n[bold green]✅ Decision Reached[/bold green]")
        console.print(f"Decision: [bold]{decision.decision}[/bold]")
        console.print(f"Rationale: {decision.rationale}")
        console.print(f"Consensus Score: {decision.consensus_score:.0%} | Confidence: {decision.overall_confidence:.0%}")
        
        table = Table(title="Cell Outputs")
        table.add_column("Role", style="cyan")
        table.add_column("Recommendation", style="magenta")
        table.add_column("Confidence", justify="right", style="green")

        for output in decision.cell_outputs:
            if output.signal_type != SignalType.ADVISORY:
                table.add_row(
                    output.cell_role.value,
                    output.recommendation,
                    f"{output.confidence:.0%}",
                )
        console.print(table)

    asyncio.run(_run())


@main.command()
@click.option("--model", default="llama3.2", help="Ollama model string to test.")
def health(model: str) -> None:
    """Check the health of the LLM backend."""
    
    async def _check() -> None:
        console.print(f"Testing Ollama backend with model: [bold]{model}[/bold]")
        backend = OllamaBackend(model=model)
        is_healthy = await backend.health_check()
        
        if is_healthy:
            console.print("[bold green]✅ Backend is healthy and ready.[/bold green]")
        else:
            console.print(
                "[bold red]❌ Backend health check failed.[/bold red]\n"
                "Ensure Ollama is running and the model is pulled (`ollama serve` and `ollama pull <model>`)."
            )

    asyncio.run(_check())


@main.command()
@click.argument("alarm_file", type=click.Path(exists=True))
def alertmind(alarm_file: str) -> None:
    """Process alarms from a JSON file using the AlertMind example."""
    if not HAS_ALERTMIND:
        console.print("[bold red]Error:[/bold red] AlertMind example not found.")
        sys.exit(1)

    async def _run_alertmind() -> None:
        try:
            with open(alarm_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            console.print(f"[bold red]Error reading file:[/bold red] {e}")
            sys.exit(1)

        backend = OllamaBackend(model="llama3.2")
        if not await backend.health_check():
             console.print("[bold red]Error:[/bold red] Ollama model 'llama3.2' is not responding.")
             sys.exit(1)

        council = create_alertmind_council()
        console.print(f"[bold blue]AlertMind Ready:[/bold blue] {council.cell_count} cells running.")

        alarms = []
        if isinstance(data, list):
            for item in data:
                alarms.append(DataCenterAlarm(**item))
        elif isinstance(data, dict):
            alarms.append(DataCenterAlarm(**data))
            
        for alarm in alarms:
            await process_alarm(alarm, council)

    asyncio.run(_run_alertmind())


@main.command()
def info() -> None:
    """Show CCA installation info."""
    try:
        from importlib.metadata import version
        v = version("cellular-council")
    except Exception:
        v = "unknown (likely installed in editable mode without hatchling)"
        
    console.print(Panel(
        f"[bold blue]🧬 Cellular Council Architecture[/bold blue]\n\n"
        f"Version: [bold]{v}[/bold]\n"
        f"Framework core installed.\n\n"
        f"[dim]Run `cca --help` for available commands.[/dim]"
    ))


if __name__ == "__main__":
    main()
