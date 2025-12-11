"""Rules service layer for pattern matching and rule management."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

import psycopg2
from psycopg2.errors import UniqueViolation

from db.connect import get_db_connection


@dataclass(frozen=True)
class Rule:
    """Represents a rule record."""

    id: str
    pattern: str
    action: str
    description: Optional[str]
    approval_threshold: int
    user_tier_thresholds: dict
    created_at: str
    updated_at: str
    is_active: bool


class RuleValidationError(Exception):
    """Raised when rule validation fails (e.g., invalid regex)."""


class RuleCreationError(Exception):
    """Raised when rule creation fails."""


class RuleLookupError(Exception):
    """Raised when rule lookup operations fail."""


class RuleUpdateError(Exception):
    """Raised when rule update operations fail."""


def validate_regex_pattern(pattern: str) -> None:
    """Validate that the pattern is a valid regular expression.
    
    Raises:
        RuleValidationError: If the pattern is not a valid regex.
    """
    try:
        re.compile(pattern)
    except re.error as exc:
        raise RuleValidationError(f"Invalid regex pattern: {exc}") from exc


def create_rule(
    pattern: str,
    action: str,
    description: Optional[str] = None,
    approval_threshold: int = 1,
    user_tier_thresholds: Optional[dict] = None
) -> Rule:
   
    validate_regex_pattern(pattern)
    
    # Validate action
    valid_actions = {"AUTO_ACCEPT", "AUTO_REJECT", "NEEDS_APPROVAL"}
    if action not in valid_actions:
        raise RuleValidationError(f"Invalid action: {action}. Must be one of {valid_actions}")
    
    # Default user tier thresholds
    if user_tier_thresholds is None:
        user_tier_thresholds = {"junior": 3, "mid": 2, "senior": 1, "lead": 1}
    
    import json
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rules (pattern, action, description, approval_threshold, user_tier_thresholds)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                RETURNING id::text, pattern, action, description, approval_threshold,
                          user_tier_thresholds::text, created_at::text, updated_at::text, is_active;
                """,
                (pattern, action, description, approval_threshold, json.dumps(user_tier_thresholds)),
            )
            record = cursor.fetchone()
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise RuleCreationError(f"Failed to create rule: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        raise RuleCreationError("Rule creation failed to return a record")
    
    return Rule(
        id=record[0],
        pattern=record[1],
        action=record[2],
        description=record[3],
        approval_threshold=record[4],
        user_tier_thresholds=json.loads(record[5]),
        created_at=record[6],
        updated_at=record[7],
        is_active=record[8],
    )


def list_rules(active_only: bool = True) -> List[Rule]:
    """List all rules, optionally filtering to active only.
    
    Args:
        active_only: If True, only return active rules
        
    Returns:
        List of Rule objects
        
    Raises:
        RuleLookupError: If lookup fails
    """
    import json
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if active_only:
                cursor.execute(
                    """
                    SELECT id::text, pattern, action, description, approval_threshold,
                           user_tier_thresholds::text, created_at::text, updated_at::text, is_active
                    FROM rules
                    WHERE is_active = TRUE
                    ORDER BY created_at ASC;
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id::text, pattern, action, description, approval_threshold,
                           user_tier_thresholds::text, created_at::text, updated_at::text, is_active
                    FROM rules
                    ORDER BY created_at ASC;
                    """
                )
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise RuleLookupError(f"Failed to list rules: {exc}") from exc
    finally:
        connection.close()
    
    return [
        Rule(
            id=record[0],
            pattern=record[1],
            action=record[2],
            description=record[3],
            approval_threshold=record[4],
            user_tier_thresholds=json.loads(record[5]),
            created_at=record[6],
            updated_at=record[7],
            is_active=record[8],
        )
        for record in records
    ]


def get_rule_by_id(rule_id: str) -> Optional[Rule]:
    """Get a specific rule by ID.
    
    Args:
        rule_id: UUID of the rule
        
    Returns:
        Rule object or None if not found
        
    Raises:
        RuleLookupError: If lookup fails
    """
    import json
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, pattern, action, description, approval_threshold,
                       user_tier_thresholds::text, created_at::text, updated_at::text, is_active
                FROM rules
                WHERE id = %s::uuid;
                """,
                (rule_id,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise RuleLookupError(f"Failed to get rule: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        return None
    
    return Rule(
        id=record[0],
        pattern=record[1],
        action=record[2],
        description=record[3],
        approval_threshold=record[4],
        user_tier_thresholds=json.loads(record[5]),
        created_at=record[6],
        updated_at=record[7],
        is_active=record[8],
    )


def update_rule(
    rule_id: str,
    pattern: Optional[str] = None,
    action: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    approval_threshold: Optional[int] = None,
    user_tier_thresholds: Optional[dict] = None
) -> Rule:
    """Update a rule.
    
    Args:
        rule_id: UUID of the rule to update
        pattern: New pattern (will be validated if provided)
        action: New action
        description: New description
        is_active: New active status
        approval_threshold: New approval threshold
        user_tier_thresholds: New user tier thresholds
        
    Returns:
        Updated Rule object
        
    Raises:
        RuleValidationError: If regex pattern is invalid
        RuleUpdateError: If update fails
    """
    # Validate pattern if provided
    if pattern is not None:
        validate_regex_pattern(pattern)
    
    # Validate action if provided
    if action is not None:
        valid_actions = {"AUTO_ACCEPT", "AUTO_REJECT", "NEEDS_APPROVAL"}
        if action not in valid_actions:
            raise RuleValidationError(f"Invalid action: {action}. Must be one of {valid_actions}")
    
    # Build dynamic update query
    import json
    updates = []
    params = []
    
    if pattern is not None:
        updates.append("pattern = %s")
        params.append(pattern)
    if action is not None:
        updates.append("action = %s")
        params.append(action)
    if description is not None:
        updates.append("description = %s")
        params.append(description)
    if is_active is not None:
        updates.append("is_active = %s")
        params.append(is_active)
    if approval_threshold is not None:
        updates.append("approval_threshold = %s")
        params.append(approval_threshold)
    if user_tier_thresholds is not None:
        updates.append("user_tier_thresholds = %s::jsonb")
        params.append(json.dumps(user_tier_thresholds))
    
    if not updates:
        raise RuleUpdateError("No fields to update")
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(rule_id)
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = f"""
                UPDATE rules
                SET {', '.join(updates)}
                WHERE id = %s::uuid
                RETURNING id::text, pattern, action, description, approval_threshold,
                          user_tier_thresholds::text, created_at::text, updated_at::text, is_active;
            """
            cursor.execute(query, params)
            record = cursor.fetchone()
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise RuleUpdateError(f"Failed to update rule: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        raise RuleUpdateError("Rule not found or update failed")
    
    import json
    return Rule(
        id=record[0],
        pattern=record[1],
        action=record[2],
        description=record[3],
        approval_threshold=record[4],
        user_tier_thresholds=json.loads(record[5]),
        created_at=record[6],
        updated_at=record[7],
        is_active=record[8],
    )


def delete_rule(rule_id: str) -> None:
    """Soft delete a rule by marking it inactive.
    
    Args:
        rule_id: UUID of the rule to delete
        
    Raises:
        RuleUpdateError: If delete fails
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE rules
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING id;
                """,
                (rule_id,),
            )
            record = cursor.fetchone()
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise RuleUpdateError(f"Failed to delete rule: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        raise RuleUpdateError("Rule not found")


def match_command_against_rules(command_text: str) -> Optional[Rule]:
    """Match a command against all active rules (first match wins).
    
    Args:
        command_text: The command to match
        
    Returns:
        The first matching Rule or None if no match
        
    Raises:
        RuleLookupError: If rule lookup fails
    """
    rules = list_rules(active_only=True)
    
    for rule in rules:
        try:
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            if pattern.search(command_text):
                return rule
        except re.error:
            # Skip rules with invalid patterns (shouldn't happen due to validation)
            continue
    
    return None


@dataclass(frozen=True)
class RuleConflict:
    """Represents a conflict between two rules."""
    
    conflicting_rule: Rule
    conflict_type: str  # 'OVERLAP', 'SUBSET', 'SUPERSET'
    test_case: str  # Example command that matches both
    severity: str  # 'HIGH' (different actions), 'LOW' (same action)


def detect_rule_conflicts(new_pattern: str, new_action: str) -> List[RuleConflict]:
    """Detect conflicts between a new rule and existing rules.
    
    Tests the new pattern against common command patterns to see if multiple
    rules would match. Conflicts are categorized by severity:
    - HIGH: Rules with different actions that match the same input
    - LOW: Rules with same action that match the same input (redundant)
    
    Args:
        new_pattern: The regex pattern for the new rule
        new_action: The action for the new rule
        
    Returns:
        List of detected conflicts
        
    Raises:
        RuleValidationError: If pattern is invalid
    """
    # Validate the new pattern
    validate_regex_pattern(new_pattern)
    new_regex = re.compile(new_pattern, re.IGNORECASE)
    
    # Get all existing active rules
    existing_rules = list_rules(active_only=True)
    
    # Test cases: common commands that users might run
    test_cases = [
        "git status",
        "git log",
        "git push",
        "git clone",
        "ls -la",
        "ls",
        "cat file.txt",
        "pwd",
        "echo hello",
        "rm -rf /",
        "rm file.txt",
        "sudo su",
        "sudo apt update",
        "chmod 777",
        "mkfs.ext4",
        "dd if=/dev/zero",
        ":(){ :|:& };:",  # fork bomb
    ]
    
    conflicts = []
    
    for existing_rule in existing_rules:
        try:
            existing_regex = re.compile(existing_rule.pattern, re.IGNORECASE)
        except re.error:
            # Skip invalid patterns
            continue
        
        # Find test cases that match both patterns
        matching_cases = []
        for test_case in test_cases:
            if new_regex.search(test_case) and existing_regex.search(test_case):
                matching_cases.append(test_case)
        
        if matching_cases:
            # Determine conflict type
            # If they match the exact same test cases, might be DUPLICATE
            # Otherwise it's an OVERLAP
            conflict_type = "OVERLAP"
            
            # Determine severity
            severity = "HIGH" if new_action != existing_rule.action else "LOW"
            
            conflicts.append(RuleConflict(
                conflicting_rule=existing_rule,
                conflict_type=conflict_type,
                test_case=matching_cases[0],  # Show first matching example
                severity=severity,
            ))
    
    return conflicts
