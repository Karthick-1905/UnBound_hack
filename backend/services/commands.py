"""Commands service layer for command execution and credit management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import psycopg2

from db.connect import get_db_connection
from services.rules import match_command_against_rules, Rule


@dataclass(frozen=True)
class Command:
    """Represents a command record."""

    id: str
    user_id: str
    command_text: str
    status: str
    matched_rule_id: Optional[str]
    credits_used: int
    output: Optional[str]
    error_message: Optional[str]
    started_at: str
    completed_at: Optional[str]
    created_at: str


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits to execute a command."""


class CommandExecutionError(Exception):
    """Raised when command execution fails."""


class CommandLookupError(Exception):
    """Raised when command lookup operations fail."""


class AuditLogError(Exception):
    """Raised when audit logging fails."""


def log_audit_entry(
    user_id: str,
    action_type: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    metadata: Optional[dict] = None,
    connection=None
) -> None:
    """Log an audit trail entry.
    
    Args:
        user_id: ID of the user performing the action
        action_type: Type of action (e.g., 'COMMAND_EXECUTED')
        resource_type: Type of resource (e.g., 'command')
        resource_id: ID of the affected resource
        old_values: Previous state (for updates)
        new_values: New state (for updates/creates)
        metadata: Additional context
        connection: Optional existing database connection
        
    Raises:
        AuditLogError: If logging fails
    """
    import json
    
    should_close = False
    if connection is None:
        connection = get_db_connection()
        should_close = True
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs 
                (user_id, action_type, resource_type, resource_id, old_values, new_values, metadata)
                VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s);
                """,
                (
                    user_id,
                    action_type,
                    resource_type,
                    resource_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    json.dumps(metadata) if metadata else None,
                ),
            )
        if should_close:
            connection.commit()
    except psycopg2.Error as exc:
        if should_close:
            connection.rollback()
        raise AuditLogError(f"Failed to log audit entry: {exc}") from exc
    finally:
        if should_close:
            connection.close()


def submit_command(user_id: str, command_text: str, username: str) -> Command:
    """Submit a command for evaluation and execution.
    
    This function:
    1. Checks user has sufficient credits
    2. Matches command against rules
    3. Executes or rejects based on rule action
    4. Deducts credits on execution
    5. Logs audit trail
    
    Args:
        user_id: ID of the user submitting the command
        command_text: The command to execute
        username: Username for audit logging
        
    Returns:
        The created Command object
        
    Raises:
        InsufficientCreditsError: If user has no credits
        CommandExecutionError: If execution fails
    """
    connection = get_db_connection()
    
    try:
        # Start transaction
        with connection.cursor() as cursor:
            # Check credit balance with row lock
            cursor.execute(
                """
                SELECT credit_balance FROM users
                WHERE id = %s::uuid
                FOR UPDATE;
                """,
                (user_id,),
            )
            balance_record = cursor.fetchone()
            
            if balance_record is None:
                raise CommandExecutionError("User not found")
            
            credit_balance = balance_record[0]
            
            if credit_balance <= 0:
                raise InsufficientCreditsError("Insufficient credits")
            
            # Match command against rules
            matched_rule = match_command_against_rules(command_text)
            
            # Determine action
            if matched_rule is None:
                # No match - default to NEEDS_APPROVAL for safety
                action = "NEEDS_APPROVAL"
                matched_rule_id = None
            else:
                action = matched_rule.action
                matched_rule_id = matched_rule.id
            
            # Handle based on action
            if action == "AUTO_REJECT":
                # Reject without deducting credits
                cursor.execute(
                    """
                    INSERT INTO commands 
                    (user_id, command_text, status, matched_rule_id, credits_used)
                    VALUES (%s::uuid, %s, 'REJECTED', %s::uuid, 0)
                    RETURNING id::text, user_id::text, command_text, status, 
                              matched_rule_id::text, credits_used, output, error_message,
                              started_at::text, completed_at::text, created_at::text;
                    """,
                    (user_id, command_text, matched_rule_id),
                )
                record = cursor.fetchone()
                
                # Log audit entry
                log_audit_entry(
                    user_id=user_id,
                    action_type="COMMAND_REJECTED",
                    resource_type="command",
                    resource_id=record[0],
                    new_values={"command_text": command_text, "status": "REJECTED"},
                    metadata={"username": username, "matched_rule_id": matched_rule_id},
                    connection=connection
                )
                
                connection.commit()
                
            elif action == "AUTO_ACCEPT":
                # Create command record as PENDING
                cursor.execute(
                    """
                    INSERT INTO commands 
                    (user_id, command_text, status, matched_rule_id, credits_used)
                    VALUES (%s::uuid, %s, 'PENDING', %s::uuid, 0)
                    RETURNING id::text;
                    """,
                    (user_id, command_text, matched_rule_id),
                )
                command_id = cursor.fetchone()[0]
                
                # Deduct credits (1 credit per execution)
                cursor.execute(
                    """
                    UPDATE users
                    SET credit_balance = credit_balance - 1
                    WHERE id = %s::uuid;
                    """,
                    (user_id,),
                )
                
                # Simulate execution (never actually run shell commands)
                simulated_output = f"[SIMULATED] Command '{command_text}' would execute here"
                
                # Update command to EXECUTED with output
                cursor.execute(
                    """
                    UPDATE commands
                    SET status = 'EXECUTED',
                        credits_used = 1,
                        output = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = %s::uuid
                    RETURNING id::text, user_id::text, command_text, status, 
                              matched_rule_id::text, credits_used, output, error_message,
                              started_at::text, completed_at::text, created_at::text;
                    """,
                    (simulated_output, command_id),
                )
                record = cursor.fetchone()
                
                # Log audit entry
                log_audit_entry(
                    user_id=user_id,
                    action_type="COMMAND_EXECUTED",
                    resource_type="command",
                    resource_id=command_id,
                    new_values={
                        "command_text": command_text,
                        "status": "EXECUTED",
                        "credits_used": 1
                    },
                    metadata={
                        "username": username,
                        "matched_rule_id": matched_rule_id,
                        "new_balance": credit_balance - 1
                    },
                    connection=connection
                )
                
                connection.commit()
                
            else:  # NEEDS_APPROVAL
                # Create command with NEEDS_APPROVAL status
                cursor.execute(
                    """
                    INSERT INTO commands 
                    (user_id, command_text, status, matched_rule_id, credits_used)
                    VALUES (%s::uuid, %s, 'NEEDS_APPROVAL', %s::uuid, 0)
                    RETURNING id::text, user_id::text, command_text, status, 
                              matched_rule_id::text, credits_used, output, error_message,
                              started_at::text, completed_at::text, created_at::text;
                    """,
                    (user_id, command_text, matched_rule_id),
                )
                record = cursor.fetchone()
                command_id = record[0]
                
                # Get user tier for threshold calculation
                cursor.execute(
                    "SELECT user_tier FROM users WHERE id = %s::uuid;",
                    (user_id,)
                )
                user_tier = cursor.fetchone()[0]
                
                # Calculate required approvals based on user tier and rule settings
                from services.approval_voting import calculate_required_approvals
                if matched_rule:
                    required_approvals = calculate_required_approvals(
                        user_tier, 
                        matched_rule.user_tier_thresholds,
                        matched_rule.approval_threshold
                    )
                else:
                    # Default if no rule matched
                    tier_defaults = {"junior": 3, "mid": 2, "senior": 1, "lead": 1}
                    required_approvals = tier_defaults.get(user_tier, 2)
                
                # Create approval request
                from services.approvals import create_approval_request, mark_notified
                approval_request = create_approval_request(
                    command_id=command_id,
                    requested_by=user_id,
                    required_approvals=required_approvals
                )
                
                # Get all admin emails
                from services.users import get_all_admin_emails
                admin_emails = get_all_admin_emails()
                
                # Send email notifications to all admins
                if admin_emails:
                    try:
                        from services.notifications import send_approval_request_email
                        send_approval_request_email(
                            to_emails=admin_emails,
                            command_text=command_text,
                            requested_by=username,
                            approval_request_id=approval_request.id,
                            command_id=command_id
                        )
                        mark_notified(approval_request.id)
                    except Exception as email_exc:
                        # Log but don't fail the command submission
                        print(f"Warning: Failed to send approval email: {email_exc}")
                
                # Log audit entry
                log_audit_entry(
                    user_id=user_id,
                    action_type="COMMAND_PENDING_APPROVAL",
                    resource_type="command",
                    resource_id=command_id,
                    new_values={
                        "command_text": command_text, 
                        "status": "NEEDS_APPROVAL",
                        "required_approvals": required_approvals
                    },
                    metadata={
                        "username": username, 
                        "matched_rule_id": matched_rule_id,
                        "user_tier": user_tier,
                        "approval_request_id": approval_request.id
                    },
                    connection=connection
                )
                
                connection.commit()
        
    except (InsufficientCreditsError, CommandExecutionError):
        connection.rollback()
        connection.close()
        raise
    except psycopg2.Error as exc:
        connection.rollback()
        connection.close()
        raise CommandExecutionError(f"Failed to execute command: {exc}") from exc
    finally:
        if connection:
            connection.close()
    
    return Command(
        id=record[0],
        user_id=record[1],
        command_text=record[2],
        status=record[3],
        matched_rule_id=record[4],
        credits_used=record[5],
        output=record[6],
        error_message=record[7],
        started_at=record[8],
        completed_at=record[9],
        created_at=record[10],
    )


def list_commands(user_id: Optional[str] = None, limit: int = 50) -> List[Command]:
    """List commands, optionally filtered by user.
    
    Args:
        user_id: If provided, only return commands for this user
        limit: Maximum number of commands to return
        
    Returns:
        List of Command objects
        
    Raises:
        CommandLookupError: If lookup fails
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if user_id:
                cursor.execute(
                    """
                    SELECT id::text, user_id::text, command_text, status, 
                           matched_rule_id::text, credits_used, output, error_message,
                           started_at::text, completed_at::text, created_at::text
                    FROM commands
                    WHERE user_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id::text, user_id::text, command_text, status, 
                           matched_rule_id::text, credits_used, output, error_message,
                           started_at::text, completed_at::text, created_at::text
                    FROM commands
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise CommandLookupError(f"Failed to list commands: {exc}") from exc
    finally:
        connection.close()
    
    return [
        Command(
            id=record[0],
            user_id=record[1],
            command_text=record[2],
            status=record[3],
            matched_rule_id=record[4],
            credits_used=record[5],
            output=record[6],
            error_message=record[7],
            started_at=record[8],
            completed_at=record[9],
            created_at=record[10],
        )
        for record in records
    ]


def get_command_by_id(command_id: str, user_id: Optional[str] = None) -> Optional[Command]:
    """Get a specific command by ID.
    
    Args:
        command_id: UUID of the command
        user_id: If provided, verify the command belongs to this user
        
    Returns:
        Command object or None if not found
        
    Raises:
        CommandLookupError: If lookup fails
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if user_id:
                cursor.execute(
                    """
                    SELECT id::text, user_id::text, command_text, status, 
                           matched_rule_id::text, credits_used, output, error_message,
                           started_at::text, completed_at::text, created_at::text
                    FROM commands
                    WHERE id = %s::uuid AND user_id = %s::uuid;
                    """,
                    (command_id, user_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id::text, user_id::text, command_text, status, 
                           matched_rule_id::text, credits_used, output, error_message,
                           started_at::text, completed_at::text, created_at::text
                    FROM commands
                    WHERE id = %s::uuid;
                    """,
                    (command_id,),
                )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise CommandLookupError(f"Failed to get command: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        return None
    
    return Command(
        id=record[0],
        user_id=record[1],
        command_text=record[2],
        status=record[3],
        matched_rule_id=record[4],
        credits_used=record[5],
        output=record[6],
        error_message=record[7],
        started_at=record[8],
        completed_at=record[9],
        created_at=record[10],
    )
