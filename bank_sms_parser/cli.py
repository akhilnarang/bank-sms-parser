"""Command-line interface for ad-hoc SMS parsing.

Examples:
    echo "<sms body>" | uv run bank-sms-parser --bank hdfc
    uv run bank-sms-parser --bank icici --body "INR 1,604.00 spent ..."
    uv run bank-sms-parser banks
"""

import datetime
import json
import sys

import typer

from bank_sms_parser import SUPPORTED_BANKS, parse_sms

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def parse(
    bank: str = typer.Option(..., "--bank", "-b", help="Bank slug (lowercase)."),
    body: str | None = typer.Option(
        None,
        "--body",
        help="SMS body. If omitted, read from stdin.",
    ),
    sender: str | None = typer.Option(None, "--sender", help="TRAI sender ID."),
    received_at: str | None = typer.Option(
        None,
        "--received-at",
        help="ISO-8601 UTC datetime (e.g. 2026-05-02T14:23:11+00:00).",
    ),
) -> None:
    """Parse a single SMS and print the structured JSON result."""
    body_text = body if body is not None else sys.stdin.read()
    received_at_dt = (
        datetime.datetime.fromisoformat(received_at) if received_at else None
    )
    result = parse_sms(
        bank, body_text, sender=sender, received_at=received_at_dt
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


@app.command()
def banks() -> None:
    """List supported bank slugs."""
    for slug in SUPPORTED_BANKS:
        typer.echo(slug)


if __name__ == "__main__":
    app()
