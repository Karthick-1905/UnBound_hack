"""Typer CLI for interacting with the UnBound Command Gateway backend."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from client import (
    BackendError,
    create_user,
    get_user_profile,
    list_rules,
    create_rule as create_rule_api,
    delete_rule as delete_rule_api,
    submit_command as submit_command_api,
    list_commands as list_commands_api,
    get_command as get_command_api,
    switch_user as switch_user_api,
)
from config import CLIConfig, load_config, save_config

app = typer.Typer(help="UnBound CLI")
console = Console()


@app.command()
def init(
    username: str = typer.Option(
        None,
        "--username",
        "-u",
        help="Username to register if no API key is stored yet.",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Override backend base URL (default http://localhost:8000).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-initialization even if an API key is already stored.",
    ),
):
    """Initialize the CLI: register user (first time) and store API key locally."""

    cfg: CLIConfig = load_config()

    if base_url:
        cfg.base_url = base_url

    if cfg.api_key and not force:
        console.print("[yellow]API key already configured. Use --force to replace it.[/yellow]")
        save_config(cfg)
        raise typer.Exit(code=0)

    if not username:
        username = typer.prompt("Enter username")

    console.print(f"Registering user '[cyan]{username}[/cyan]' against {cfg.base_url} ...")
    try:
        user_id, api_key = create_user(cfg, username)
    except BackendError as exc:
        console.print(f"[red]Failed to create user: {exc.detail} (status {exc.status_code})[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Unexpected error: {exc}[/red]")
        raise typer.Exit(code=1)

    cfg.api_key = api_key
    save_config(cfg)
    console.print("[green]User created successfully.[/green]")
    console.print(f"User ID: {user_id}")
    console.print("[yellow]API key stored locally (not displayed again).[/yellow]")


@app.command()
def status():
    """Show current CLI configuration and user profile."""

    cfg = load_config()
    if not cfg.api_key:
        console.print("[yellow]No API key configured. Run `unbound init`.[/yellow]")
        console.print(f"Backend: {cfg.base_url}")
        raise typer.Exit(code=0)

    console.print(f"Backend: {cfg.base_url}")
    
    try:
        profile = get_user_profile(cfg)
        console.print(f"[cyan]Username:[/cyan] {profile['username']}")
        console.print(f"[cyan]Role:[/cyan] {profile['role']}")
        console.print(f"[cyan]Credits:[/cyan] {profile['credit_balance']}")
    except BackendError as exc:
        console.print(f"[red]Failed to get profile: {exc.detail}[/red]")
        raise typer.Exit(code=1)


# Rule management commands (admin only)
rules_app = typer.Typer(help="Manage rules (admin only)")
app.add_typer(rules_app, name="rules")


@rules_app.command("list")
def rules_list(
    all: bool = typer.Option(False, "--all", help="Show inactive rules too")
):
    """List all rules."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    try:
        rules = list_rules(cfg, active_only=not all)
        
        if not rules:
            console.print("[yellow]No rules found.[/yellow]")
            return
        
        table = Table(title="Rules")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Pattern", style="magenta")
        table.add_column("Action", style="green")
        table.add_column("Description")
        table.add_column("Active", style="yellow")
        
        for rule in rules:
            table.add_row(
                rule["id"][:8] + "...",
                rule["pattern"],
                rule["action"],
                rule["description"] or "",
                "✓" if rule["is_active"] else "✗",
            )
        
        console.print(table)
        
    except BackendError as exc:
        console.print(f"[red]Failed to list rules: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@rules_app.command("add")
def rules_add(
    pattern: str = typer.Argument(..., help="Regex pattern to match commands"),
    action: str = typer.Argument(
        ...,
        help="Action: AUTO_ACCEPT, AUTO_REJECT, or NEEDS_APPROVAL"
    ),
    description: str = typer.Option(None, "--description", "-d", help="Rule description"),
):
    """Create a new rule."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    action = action.upper()
    valid_actions = {"AUTO_ACCEPT", "AUTO_REJECT", "NEEDS_APPROVAL"}
    if action not in valid_actions:
        console.print(f"[red]Invalid action. Must be one of: {', '.join(valid_actions)}[/red]")
        raise typer.Exit(code=1)

    try:
        rule = create_rule_api(cfg, pattern, action, description)
        console.print("[green]Rule created successfully![/green]")
        console.print(f"ID: {rule['id']}")
        console.print(f"Pattern: {rule['pattern']}")
        console.print(f"Action: {rule['action']}")
        
    except BackendError as exc:
        console.print(f"[red]Failed to create rule: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@rules_app.command("delete")
def rules_delete(
    rule_id: str = typer.Argument(..., help="ID of the rule to delete"),
):
    """Delete (soft-delete) a rule."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    try:
        delete_rule_api(cfg, rule_id)
        console.print("[green]Rule deleted successfully.[/green]")
        
    except BackendError as exc:
        console.print(f"[red]Failed to delete rule: {exc.detail}[/red]")
        raise typer.Exit(code=1)


# Command submission and management
commands_app = typer.Typer(help="Submit and manage commands")
app.add_typer(commands_app, name="commands")


@commands_app.command("submit")
def commands_submit(
    command_text: str = typer.Argument(..., help="Command to execute"),
):
    """Submit a command for execution."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    try:
        result = submit_command_api(cfg, command_text)
        command = result["command"]
        new_balance = result["new_credit_balance"]
        
        status = command["status"]
        if status == "EXECUTED":
            console.print(f"[green]✓ Command executed successfully[/green]")
            if command["output"]:
                console.print(f"[dim]{command['output']}[/dim]")
        elif status == "REJECTED":
            console.print(f"[red]✗ Command rejected by rules[/red]")
        elif status == "NEEDS_APPROVAL":
            console.print(f"[yellow]⚠ Command needs admin approval[/yellow]")
        
        console.print(f"[cyan]Credits used:[/cyan] {command['credits_used']}")
        console.print(f"[cyan]New balance:[/cyan] {new_balance}")
        console.print(f"[dim]Command ID: {command['id']}[/dim]")
        
    except BackendError as exc:
        console.print(f"[red]Failed to submit command: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@commands_app.command("list")
def commands_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of commands to show"),
):
    """List recent commands."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    try:
        commands = list_commands_api(cfg, limit=limit)
        
        if not commands:
            console.print("[yellow]No commands found.[/yellow]")
            return
        
        table = Table(title="Commands")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Command", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Credits", justify="right")
        table.add_column("Created", style="dim")
        
        for cmd in commands:
            status_color = {
                "EXECUTED": "green",
                "REJECTED": "red",
                "NEEDS_APPROVAL": "yellow",
                "PENDING": "blue",
                "FAILED": "red",
            }.get(cmd["status"], "white")
            
            table.add_row(
                cmd["id"][:8] + "...",
                cmd["command_text"][:50] + ("..." if len(cmd["command_text"]) > 50 else ""),
                f"[{status_color}]{cmd['status']}[/{status_color}]",
                str(cmd["credits_used"]),
                cmd["created_at"][:19],
            )
        
        console.print(table)
        
    except BackendError as exc:
        console.print(f"[red]Failed to list commands: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@commands_app.command("get")
def commands_get(
    command_id: str = typer.Argument(..., help="ID of the command to view"),
):
    """Get detailed information about a command."""
    cfg = load_config()
    if not cfg.api_key:
        console.print("[red]Not authenticated. Run `unbound init` first.[/red]")
        raise typer.Exit(code=1)

    try:
        cmd = get_command_api(cfg, command_id)
        
        console.print(f"[cyan]Command ID:[/cyan] {cmd['id']}")
        console.print(f"[cyan]Status:[/cyan] {cmd['status']}")
        console.print(f"[cyan]Command:[/cyan] {cmd['command_text']}")
        console.print(f"[cyan]Credits Used:[/cyan] {cmd['credits_used']}")
        console.print(f"[cyan]Created:[/cyan] {cmd['created_at']}")
        
        if cmd["output"]:
            console.print(f"[cyan]Output:[/cyan]\n{cmd['output']}")
        
        if cmd["error_message"]:
            console.print(f"[red]Error:[/red] {cmd['error_message']}")
        
    except BackendError as exc:
        console.print(f"[red]Failed to get command: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@app.command()
def switch(
    username: str = typer.Argument(..., help="Username to switch to"),
):
    """Switch to a different user (no password required - testing mode only)."""
    cfg = load_config()
    
    try:
        user_id, api_key = switch_user_api(cfg, username)
        cfg.api_key = api_key
        save_config(cfg)
        
        console.print(f"[green]✓ Switched to user '{username}'[/green]")
        console.print(f"[dim]User ID: {user_id}[/dim]")
        
        # Show new profile
        profile = get_user_profile(cfg)
        console.print(f"[cyan]Role:[/cyan] {profile['role']}")
        console.print(f"[cyan]Credits:[/cyan] {profile['credit_balance']}")
        
    except BackendError as exc:
        console.print(f"[red]Failed to switch user: {exc.detail}[/red]")
        raise typer.Exit(code=1)


@app.command()
def shell():
    """Launch interactive shell (REPL mode)."""
    try:
        from shell import main as shell_main
        shell_main()
    except ImportError:
        console.print("[red]Shell module not found. Make sure shell.py is in the same directory.[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()