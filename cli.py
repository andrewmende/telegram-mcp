"""CLI for the Telegram MCP server — login, start, clear-session."""

import asyncio
import logging
import os
import sys
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from server import mcp
from telegram import Telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = typer.Typer(
    name="telegram-mcp",
    help="Telegram MTProto MCP Server",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def async_command(func: Callable[..., Coroutine[Any, Any, None]]) -> Callable[..., None]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        asyncio.run(func(*args, **kwargs))
    return wrapper


@app.command()
@async_command
async def login() -> None:
    """Authenticate with Telegram and save a local session file."""
    console.print(
        Panel.fit(
            "[bold blue]Telegram MCP — Login[/bold blue]\n\n"
            "You need Telegram API credentials:\n"
            "1. Visit [link]https://my.telegram.org/apps[/link]\n"
            "2. Create an application\n"
            "3. Copy your API ID and API Hash",
            title="Authentication",
            border_style="blue",
        )
    )

    tg = Telegram()

    try:
        api_id = console.input("\n[bold cyan]API ID[/bold cyan] > ", password=True)
        api_hash = console.input("\n[bold cyan]API Hash[/bold cyan] > ", password=True)
        phone = console.input("\n[bold cyan]Phone number[/bold cyan] (e.g. +1234567890) > ")

        tg.create_client(api_id=api_id, api_hash=api_hash)

        with console.status("Connecting to Telegram...", spinner="dots"):
            await tg.client.connect()

        def code_callback() -> str:
            return console.input("\n[bold cyan]Verification code[/bold cyan] > ")

        def password_callback() -> str:
            return console.input("\n[bold cyan]2FA password[/bold cyan] > ", password=True)

        await tg.client.start(phone=phone, code_callback=code_callback, password=password_callback)  # type: ignore

        tg.save_session_string()
        user = await tg.client.get_me()
        console.print(
            Panel.fit(
                f"[bold green]Logged in as {user.first_name}[/bold green]\n"  # type: ignore
                "[dim]Run `python cli.py start` to launch the MCP server.[/dim]",
                title="Success",
                border_style="green",
            )
        )
    except ValueError:
        console.print("[bold red]Error:[/bold red] API ID must be a number")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)
    finally:
        if tg.client.is_connected():
            tg.client.disconnect()


@app.command()
def start(
    http: bool = typer.Option(False, "--http", help="Serve over streamable HTTP instead of stdio."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (HTTP mode)."),
    port: int = typer.Option(8765, "--port", help="Bind port (HTTP mode)."),
    path: str = typer.Option("/telegram", "--path", help="HTTP endpoint path (HTTP mode)."),
) -> None:
    """Start the MCP server (requires a saved session from `login`).

    Defaults to stdio for local MCP clients. Pass --http to serve over the
    network (e.g. behind nginx); set MCP_TOKEN to require bearer-token auth.
    """
    if http:
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        mcp.run()


@app.command()
def clear_session() -> None:
    """Delete the local Telegram session file."""
    session_file = Telegram().session_file.with_suffix(".session")
    if session_file.exists():
        try:
            os.remove(session_file)
            console.print("[bold green]Session file deleted.[/bold green]")
        except Exception as exc:
            console.print(f"[bold red]Failed to delete session:[/bold red] {exc}")
    else:
        console.print("[yellow]No session file found.[/yellow]")


@app.command()
def logout() -> None:
    """Instructions for revoking the active session from your Telegram account."""
    console.print(
        Panel.fit(
            "To revoke access:\n"
            "1. Open Telegram → Settings → Privacy and Security → Active Sessions\n"
            "2. Find the session matching your app name and terminate it\n"
            "3. Run [bold]clear-session[/bold] to remove the local file",
            title="Logout",
            border_style="blue",
        )
    )


if __name__ == "__main__":
    app()
