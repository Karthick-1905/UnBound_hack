"""Interactive REPL shell for UnBound Command Gateway using cmd2."""

from __future__ import annotations

import cmd2
from rich.console import Console
from rich.table import Table

from client import (
    BackendError,
    get_user_profile,
    list_rules,
    create_rule as create_rule_api,
    delete_rule as delete_rule_api,
    submit_command as submit_command_api,
    list_commands as list_commands_api,
    get_command as get_command_api,
    switch_user as switch_user_api,
    list_audit_logs as list_audit_logs_api,
    get_audit_log as get_audit_log_api,
)
from config import CLIConfig, load_config, save_config


class UnboundShell(cmd2.Cmd):
    """Interactive shell for UnBound Command Gateway."""

    intro = """
╔════════════════════════════════════════════════════════╗
║        UnBound Command Gateway - Interactive Shell      ║
╚════════════════════════════════════════════════════════╝

Type 'help' or '?' to list commands.
Type 'exit' or 'quit' to exit.

Any command not recognized as a shell command will be sent
to the backend for evaluation and execution.
"""
    prompt = "unbound> "

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()
        self.cfg = load_config()
        
        if not self.cfg.api_key:
            self.console.print("[yellow]⚠ No API key configured. Please run 'init' to set up your account.[/yellow]")
        else:
            self._update_prompt()

    def _update_prompt(self):
        """Update prompt with user info."""
        try:
            profile = get_user_profile(self.cfg)
            username = profile.get('username', 'unknown')
            role = profile.get('role', 'unknown')
            credits = profile.get('credit_balance', 0)
            
            color = "cyan" if role == "admin" else "green"
            self.prompt = f"[{color}]{username}@unbound[/{color}] ({credits} credits)> "
        except Exception:
            self.prompt = "unbound> "

    def default(self, statement):
        """Handle any command that doesn't match a defined command.
        
        This is called by cmd2 when a command is not recognized.
        We send it to the backend for evaluation and execution.
        """
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated. Please configure API key first.[/red]")
            return
        
        # Get the full command line (command + arguments)
        # Handle both cmd2 statement objects and plain strings
        if hasattr(statement, 'raw'):
            command_text = statement.raw
        else:
            command_text = str(statement)
        
        if not command_text.strip():
            return
        
        # Don't send help-related commands
        if command_text.strip() in ['?', 'help', 'exit', 'quit', 'EOF']:
            return super().default(statement)
        
        # Send to backend for execution
        try:
            result = submit_command_api(self.cfg, command_text)
            command = result["command"]
            new_balance = result["new_credit_balance"]
            matched_rule = command.get("matched_rule_id")
            
            status = command["status"]
            if status == "EXECUTED":
                self.console.print(f"[green]✓ Command executed successfully[/green]")
                if command["output"]:
                    self.console.print(f"[dim]{command['output']}[/dim]")
                if matched_rule:
                    self.console.print(f"[dim]Matched rule: {matched_rule[:8]}...[/dim]")
            elif status == "REJECTED":
                self.console.print(f"[red]✗ Command rejected by security rules[/red]")
                if matched_rule:
                    self.console.print(f"[dim]Matched rule: {matched_rule[:8]}...[/dim]")
            elif status == "NEEDS_APPROVAL":
                self.console.print(f"[yellow]⚠ Command needs admin approval (no rule matched)[/yellow]")
            
            self.console.print(f"[cyan]Credits used:[/cyan] {command['credits_used']} | [cyan]Balance:[/cyan] {new_balance}")
            
            # Update prompt with new balance
            self._update_prompt()
            
        except BackendError as exc:
            if exc.status_code == 402:
                self.console.print(f"[red]✗ Insufficient credits[/red]")
                self.console.print("[yellow]You need more credits to execute commands.[/yellow]")
            else:
                self.console.print(f"[red]Failed to execute command: {exc.detail}[/red]")

    def do_init(self, _):
        """Initialize or login to your account. Creates new user or logs in to existing."""
        self.console.print("\n[cyan]═══════════════════════════════════════════════════[/cyan]")
        self.console.print("[cyan]          UnBound Command Gateway - Login/Signup     [/cyan]")
        self.console.print("[cyan]═══════════════════════════════════════════════════[/cyan]\n")
        
        # Get username
        username = input("Enter your username: ").strip()
        while not username:
            self.console.print("[red]Username cannot be empty.[/red]")
            username = input("Enter your username: ").strip()
        
        # Get email (optional but recommended)
        self.console.print("\n[dim]Email is optional but recommended for approval notifications.[/dim]")
        email = input("Enter your email (or press Enter to skip): ").strip()
        if not email:
            email = None
        
        # Try to login/create user
        self.console.print(f"\n[cyan]Checking account for '{username}'...[/cyan]")
        
        try:
            from client import create_user, switch_user
            
            # Try to switch to existing user first (login)
            try:
                user_id, api_key = switch_user(self.cfg, username)
                
                # Save config
                self.cfg.api_key = api_key
                save_config(self.cfg)
                
                self.console.print(f"[green]✓ Logged in as '{username}'![/green]")
                self.console.print(f"[dim]User ID: {user_id}[/dim]")
                self.console.print(f"[yellow]API Key: {api_key}[/yellow]")
                self.console.print("\n[cyan]Your API key has been saved to .unbound_config.json[/cyan]")
                self.console.print("[dim]Keep this key secure - it won't be shown again![/dim]\n")
                
            except BackendError as be:
                # If user doesn't exist, create new user
                if be.status_code == 404:
                    self.console.print(f"[yellow]User '{username}' not found. Creating new account...[/yellow]")
                    
                    user_id, api_key = create_user(self.cfg, username, email)
                    
                    # Save config
                    self.cfg.api_key = api_key
                    save_config(self.cfg)
                    
                    self.console.print("[green]✓ User created successfully![/green]")
                    self.console.print(f"[dim]User ID: {user_id}[/dim]")
                    self.console.print(f"[yellow]API Key: {api_key}[/yellow]")
                    self.console.print("\n[cyan]Your API key has been saved to .unbound_config.json[/cyan]")
                    self.console.print("[dim]Keep this key secure - it won't be shown again![/dim]\n")
                else:
                    raise
            
            # Update prompt
            self._update_prompt()
            
        except BackendError as exc:
            self.console.print(f"[red]Failed: {exc.detail}[/red]")
            self.console.print("[yellow]Please check that the backend server is running.[/yellow]")
        except Exception as exc:
            self.console.print(f"[red]Error: {exc}[/red]")

    def do_status(self, _):
        """Show current user profile and configuration."""
        if not self.cfg.api_key:
            self.console.print("[yellow]Not authenticated. Please run init first.[/yellow]")
            return

        self.console.print(f"[dim]Backend: {self.cfg.base_url}[/dim]")
        
        try:
            profile = get_user_profile(self.cfg)
            self.console.print(f"[cyan]Username:[/cyan] {profile['username']}")
            self.console.print(f"[cyan]Role:[/cyan] {profile['role']}")
            
            # Display user tier with explanation
            tier = profile.get('user_tier', 'junior')
            tier_approvals = {'junior': 3, 'mid': 2, 'senior': 1, 'lead': 1}
            required = tier_approvals.get(tier, 3)
            self.console.print(f"[cyan]Tier:[/cyan] {tier} [dim](requires {required} approval{'s' if required > 1 else ''})[/dim]")
            
            self.console.print(f"[cyan]Credits:[/cyan] {profile['credit_balance']}")
            self._update_prompt()
        except BackendError as exc:
            self.console.print(f"[red]Failed to get profile: {exc.detail}[/red]")

    def do_rules_list(self, args):
        """List all rules. Usage: rules_list [--all]"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        show_all = "--all" in args or "-a" in args

        try:
            rules = list_rules(self.cfg, active_only=not show_all)
            
            if not rules:
                self.console.print("[yellow]No rules found.[/yellow]")
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
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to list rules: {exc.detail}[/red]")

    def do_rules_add(self, args):
        """Add a new rule. Usage: rules_add <pattern> <action> [description] [--threshold N] [--tier-thresholds "junior:3,mid:2,senior:1,lead:1"]
        
        Example: rules_add "^sudo" AUTO_REJECT "Block sudo commands"
        Example: rules_add "^docker" NEEDS_APPROVAL "Requires approval" --threshold 2
        Example: rules_add "^systemctl" NEEDS_APPROVAL "Service control" --tier-thresholds "junior:3,mid:2,senior:1"
        """
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        parts = args.split()
        if len(parts) < 2:
            self.console.print("[red]Usage: rules_add <pattern> <action> [description] [--threshold N] [--tier-thresholds \"...\"][/red]")
            self.console.print("[dim]Example: rules_add \"^sudo\" AUTO_REJECT \"Block sudo\"[/dim]")
            return

        pattern = parts[0].strip('"\'')
        action = parts[1].upper().strip('"\'')
        
        # Parse optional description and flags
        description = None
        approval_threshold = None
        user_tier_thresholds = None
        i = 2
        
        while i < len(parts):
            if parts[i] == "--threshold" and i + 1 < len(parts):
                approval_threshold = int(parts[i + 1])
                i += 2
            elif parts[i] == "--tier-thresholds" and i + 1 < len(parts):
                # Parse "junior:3,mid:2,senior:1,lead:1" format
                tier_str = parts[i + 1].strip('"\'')
                user_tier_thresholds = {}
                for pair in tier_str.split(','):
                    tier, threshold = pair.split(':')
                    user_tier_thresholds[tier.strip()] = int(threshold.strip())
                i += 2
            elif not parts[i].startswith('--'):
                # It's the description
                description = parts[i].strip('"\'')
                i += 1
            else:
                i += 1

        valid_actions = {"AUTO_ACCEPT", "AUTO_REJECT", "NEEDS_APPROVAL"}
        if action not in valid_actions:
            self.console.print(f"[red]Invalid action. Must be one of: {', '.join(valid_actions)}[/red]")
            return

        try:
            rule = create_rule_api(
                self.cfg, 
                pattern, 
                action, 
                description, 
                approval_threshold=approval_threshold,
                user_tier_thresholds=user_tier_thresholds
            )
            self.console.print("[green]✓ Rule created successfully![/green]")
            self.console.print(f"[dim]ID: {rule['id']}[/dim]")
            self.console.print(f"Pattern: {rule['pattern']}")
            self.console.print(f"Action: {rule['action']}")
            
            if rule.get('approval_threshold'):
                self.console.print(f"[dim]Approval Threshold: {rule['approval_threshold']}[/dim]")
            if rule.get('user_tier_thresholds'):
                self.console.print(f"[dim]User Tier Thresholds: {rule['user_tier_thresholds']}[/dim]")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to create rule: {exc.detail}[/red]")

    def do_rules_update(self, args):
        """Update a rule. Usage: rules_update <rule_id> [--pattern "..."] [--action ...] [--description "..."] [--active true|false]"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        parts = args.split(maxsplit=1)
        if not parts:
            self.console.print("[red]Usage: rules_update <rule_id> [--pattern \"...\"] [--action ...] [--description \"...\"] [--active true|false][/red]")
            return

        rule_id = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        
        # Parse optional flags
        pattern = None
        action = None
        description = None
        is_active = None
        
        import shlex
        try:
            tokens = shlex.split(rest)
            i = 0
            while i < len(tokens):
                if tokens[i] == "--pattern" and i + 1 < len(tokens):
                    pattern = tokens[i + 1]
                    i += 2
                elif tokens[i] == "--action" and i + 1 < len(tokens):
                    action = tokens[i + 1]
                    i += 2
                elif tokens[i] == "--description" and i + 1 < len(tokens):
                    description = tokens[i + 1]
                    i += 2
                elif tokens[i] == "--active" and i + 1 < len(tokens):
                    val = tokens[i + 1].lower()
                    if val in ("true", "1", "yes"):
                        is_active = True
                    elif val in ("false", "0", "no"):
                        is_active = False
                    else:
                        self.console.print(f"[red]Invalid value for --active: {tokens[i + 1]}[/red]")
                        return
                    i += 2
                else:
                    i += 1
        except ValueError as e:
            self.console.print(f"[red]Failed to parse arguments: {e}[/red]")
            return

        if not any([pattern, action, description, is_active is not None]):
            self.console.print("[yellow]No changes specified. Use --pattern, --action, --description, or --active.[/yellow]")
            return

        try:
            from client import update_rule as update_rule_api
            updated_rule = update_rule_api(self.cfg, rule_id, pattern=pattern, action=action, description=description, is_active=is_active)
            self.console.print("[green]✓ Rule updated successfully.[/green]")
            
            # Show updated rule
            table = Table(title="Updated Rule")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("ID", updated_rule['id'])
            table.add_row("Pattern", updated_rule['pattern'])
            table.add_row("Action", updated_rule['action'])
            table.add_row("Description", updated_rule.get('description', ''))
            table.add_row("Active", "Yes" if updated_rule.get('is_active', True) else "No")
            table.add_row("Created", updated_rule.get('created_at', ''))
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to update rule: {exc.detail}[/red]")

    def complete_rules_update(self, text, line, begidx, endidx):
        """Auto-complete rule IDs for rules_update command."""
        try:
            rules = list_rules(self.cfg)
            rule_ids = [rule['id'] for rule in rules]
            return [rid for rid in rule_ids if rid.startswith(text)]
        except:
            return []

    def do_rules_delete(self, args):
        """Delete a rule. Usage: rules_delete <rule_id>"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        rule_id = args.strip()
        if not rule_id:
            self.console.print("[red]Usage: rules_delete <rule_id>[/red]")
            return

        try:
            delete_rule_api(self.cfg, rule_id)
            self.console.print("[green]✓ Rule deleted successfully.[/green]")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to delete rule: {exc.detail}[/red]")
    
    def complete_rules_delete(self, text, line, begidx, endidx):
        """Auto-complete rule IDs for rules_delete command."""
        try:
            rules = list_rules(self.cfg)
            rule_ids = [rule['id'] for rule in rules]
            return [rid for rid in rule_ids if rid.startswith(text)]
        except:
            return []



    def do_history(self, args):
        """Show command history. Usage: history [limit]
        
        Example: history 10
        """
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        try:
            limit = int(args.strip()) if args.strip() else 20
        except ValueError:
            limit = 20

        try:
            commands = list_commands_api(self.cfg, limit=limit)
            
            if not commands:
                self.console.print("[yellow]No commands found.[/yellow]")
                return
            
            table = Table(title=f"Recent Commands (Last {len(commands)})")
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
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to list commands: {exc.detail}[/red]")

    def do_cmd_info(self, args):
        """Get detailed info about a command. Usage: cmd_info <command_id>"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        command_id = args.strip()
        if not command_id:
            self.console.print("[red]Usage: cmd_info <command_id>[/red]")
            return

        try:
            cmd = get_command_api(self.cfg, command_id)
            
            self.console.print(f"[cyan]Command ID:[/cyan] {cmd['id']}")
            self.console.print(f"[cyan]Status:[/cyan] {cmd['status']}")
            self.console.print(f"[cyan]Command:[/cyan] {cmd['command_text']}")
            self.console.print(f"[cyan]Credits Used:[/cyan] {cmd['credits_used']}")
            self.console.print(f"[cyan]Created:[/cyan] {cmd['created_at']}")
            
            if cmd["output"]:
                self.console.print(f"[cyan]Output:[/cyan]\n{cmd['output']}")
            
            if cmd["error_message"]:
                self.console.print(f"[red]Error:[/red] {cmd['error_message']}")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to get command: {exc.detail}[/red]")

    def do_refresh(self, _):
        """Refresh user profile and update prompt."""
        self.do_status(_)

    def do_clear(self, _):
        """Clear the screen."""
        self.console.clear()

    def do_switch_user(self, args):
        """Switch to a different user. Usage: switch_user <username>
        
        Example: switch_user member
        
        Note: No password required (testing mode only)
        """
        username = args.strip()
        if not username:
            self.console.print("[red]Usage: switch_user <username>[/red]")
            return

        try:
            user_id, api_key = switch_user_api(self.cfg, username)
            self.cfg.api_key = api_key
            save_config(self.cfg)
            
            self.console.print(f"[green]✓ Switched to user '{username}'[/green]")
            self.console.print(f"[dim]User ID: {user_id}[/dim]")
            self._update_prompt()
            
            # Show new profile
            self.do_status("")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to switch user: {exc.detail}[/red]")

    def do_audit_list(self, args):
        """List audit logs (admin only). Usage: audit_list [limit] [--action <type>] [--resource <type>]
        
        Examples:
            audit_list
            audit_list 50
            audit_list --action COMMAND_EXECUTED
            audit_list --resource command
        """
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        # Parse arguments
        parts = args.split()
        limit = 50
        action_type = None
        resource_type = None
        
        i = 0
        while i < len(parts):
            if parts[i].isdigit():
                limit = int(parts[i])
            elif parts[i] == "--action" and i + 1 < len(parts):
                action_type = parts[i + 1]
                i += 1
            elif parts[i] == "--resource" and i + 1 < len(parts):
                resource_type = parts[i + 1]
                i += 1
            i += 1

        try:
            logs = list_audit_logs_api(
                self.cfg,
                limit=limit,
                action_type=action_type,
                resource_type=resource_type
            )
            
            if not logs:
                self.console.print("[yellow]No audit logs found.[/yellow]")
                return
            
            table = Table(title=f"Audit Logs (Last {len(logs)})")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Action", style="magenta")
            table.add_column("Resource", style="green")
            table.add_column("User ID", style="blue", no_wrap=True)
            table.add_column("Created", style="dim")
            
            for log in logs:
                table.add_row(
                    log["id"][:8] + "...",
                    log["action_type"],
                    log["resource_type"] or "-",
                    log["user_id"][:8] + "..." if log["user_id"] else "-",
                    log["created_at"][:19],
                )
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to list audit logs: {exc.detail}[/red]")

    def do_audit_info(self, args):
        """Get detailed audit log info. Usage: audit_info <log_id>"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        log_id = args.strip()
        if not log_id:
            self.console.print("[red]Usage: audit_info <log_id>[/red]")
            return

        try:
            log = get_audit_log_api(self.cfg, log_id)
            
            self.console.print(f"[cyan]Log ID:[/cyan] {log['id']}")
            self.console.print(f"[cyan]Action:[/cyan] {log['action_type']}")
            self.console.print(f"[cyan]Resource Type:[/cyan] {log['resource_type'] or 'N/A'}")
            self.console.print(f"[cyan]Resource ID:[/cyan] {log['resource_id'] or 'N/A'}")
            self.console.print(f"[cyan]User ID:[/cyan] {log['user_id'] or 'N/A'}")
            self.console.print(f"[cyan]Created:[/cyan] {log['created_at']}")
            
            if log.get("metadata"):
                self.console.print(f"[cyan]Metadata:[/cyan] {log['metadata']}")
            
            if log.get("new_values"):
                self.console.print(f"[cyan]New Values:[/cyan] {log['new_values']}")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to get audit log: {exc.detail}[/red]")

    def do_approvals_list(self, args):
        """List approval requests. Usage: approvals_list [--status PENDING|APPROVED|REJECTED] [--limit 50]"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        parts = args.split()
        status = None
        limit = 50
        
        i = 0
        while i < len(parts):
            if parts[i] == "--status" and i + 1 < len(parts):
                status = parts[i + 1].upper()
                i += 2
            elif parts[i] == "--limit" and i + 1 < len(parts):
                limit = int(parts[i + 1])
                i += 2
            else:
                i += 1
        
        try:
            from client import list_approvals as list_approvals_api
            approvals = list_approvals_api(self.cfg, status=status, limit=limit)
            
            if not approvals:
                self.console.print("[yellow]No approval requests found.[/yellow]")
                return
            
            table = Table(title=f"Approval Requests ({len(approvals)})")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Command ID", style="white")
            table.add_column("Status", style="yellow")
            table.add_column("Approvals", style="green")
            table.add_column("Expires", style="magenta")
            
            for approval in approvals:
                approval_id_short = approval['id'][:8]
                command_id_short = approval['command_id'][:8]
                status_display = approval['status']
                approvals_display = f"{approval['current_approvals']}/{approval['required_approvals']}"
                expires_at = approval['expires_at'][:19] if approval['expires_at'] else "N/A"
                
                table.add_row(
                    approval_id_short,
                    command_id_short,
                    status_display,
                    approvals_display,
                    expires_at
                )
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to list approvals: {exc.detail}[/red]")

    def do_approvals_vote(self, args):
        """Vote on an approval request. Usage: approvals_vote <approval_id> APPROVE|REJECT [comment]"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        parts = args.split(maxsplit=2)
        if len(parts) < 2:
            self.console.print("[red]Usage: approvals_vote <approval_id> APPROVE|REJECT [comment][/red]")
            return
        
        approval_id = parts[0]
        vote = parts[1].upper()
        comment = parts[2] if len(parts) > 2 else None
        
        if vote not in ('APPROVE', 'REJECT'):
            self.console.print("[red]Vote must be APPROVE or REJECT[/red]")
            return
        
        try:
            from client import vote_on_approval as vote_on_approval_api
            result = vote_on_approval_api(self.cfg, approval_id, vote, comment)
            
            vote_emoji = "✅" if vote == "APPROVE" else "❌"
            self.console.print(f"[green]{vote_emoji} Vote cast: {vote}[/green]")
            
            if comment:
                self.console.print(f"[dim]Comment: {comment}[/dim]")
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to vote: {exc.detail}[/red]")

    def do_approvals_votes(self, args):
        """List votes for an approval request. Usage: approvals_votes <approval_id>"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        approval_id = args.strip()
        if not approval_id:
            self.console.print("[red]Usage: approvals_votes <approval_id>[/red]")
            return
        
        try:
            from client import list_approval_votes as list_approval_votes_api
            votes = list_approval_votes_api(self.cfg, approval_id)
            
            if not votes:
                self.console.print("[yellow]No votes yet for this approval request.[/yellow]")
                return
            
            table = Table(title=f"Votes for Approval {approval_id[:8]}")
            table.add_column("Admin", style="cyan")
            table.add_column("Vote", style="yellow")
            table.add_column("Comment", style="white")
            table.add_column("Time", style="magenta")
            
            for vote in votes:
                vote_emoji = "✅" if vote['vote'] == 'APPROVE' else "❌"
                vote_display = f"{vote_emoji} {vote['vote']}"
                admin_name = vote.get('admin_username', vote['admin_id'][:8])
                comment_text = vote.get('comment', '')[:50] if vote.get('comment') else '-'
                created_at = vote['created_at'][:19]
                
                table.add_row(
                    admin_name,
                    vote_display,
                    comment_text,
                    created_at
                )
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to list votes: {exc.detail}[/red]")

    def do_approvals_info(self, args):
        """Get detailed info about an approval request. Usage: approvals_info <approval_id>"""
        if not self.cfg.api_key:
            self.console.print("[red]Not authenticated.[/red]")
            return

        approval_id = args.strip()
        if not approval_id:
            self.console.print("[red]Usage: approvals_info <approval_id>[/red]")
            return
        
        try:
            from client import get_approval as get_approval_api
            approval = get_approval_api(self.cfg, approval_id)
            
            table = Table(title="Approval Request Details")
            table.add_column("Field", style="cyan", no_wrap=True)
            table.add_column("Value", style="white")
            
            table.add_row("ID", approval['id'])
            table.add_row("Command ID", approval['command_id'])
            table.add_row("Requested By", approval['requested_by'])
            table.add_row("Status", approval['status'])
            table.add_row("Required Approvals", str(approval['required_approvals']))
            table.add_row("Current Approvals", str(approval['current_approvals']))
            table.add_row("Expires At", approval['expires_at'][:19] if approval['expires_at'] else 'N/A')
            table.add_row("Created At", approval['created_at'][:19])
            
            if approval.get('rejection_reason'):
                table.add_row("Rejection Reason", approval['rejection_reason'])
            
            self.console.print(table)
            
        except BackendError as exc:
            self.console.print(f"[red]Failed to get approval info: {exc.detail}[/red]")


    # Shortcuts
    do_r = do_rules_list
    do_ra = do_rules_add
    do_rd = do_rules_delete
    do_h = do_history
    do_s = do_status
    do_su = do_switch_user
    do_a = do_audit_list
    do_appr = do_approvals_list


def main():
    """Entry point for the interactive shell."""
    import sys
    
    shell = UnboundShell()
    
    # Check if API key is configured
    if not shell.cfg.api_key:
        shell.console.print("[yellow]No API key found. Please run the init command first:[/yellow]")
        shell.console.print("[cyan]python3 main.py init --username <your-username>[/cyan]")
        shell.console.print("")
    
    shell.cmdloop()


if __name__ == "__main__":
    main()
