"""Audit log service layer for querying audit trails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import psycopg2

from db.connect import get_db_connection


@dataclass(frozen=True)
class AuditLog:
    """Represents an audit log entry."""

    id: str
    user_id: Optional[str]
    action_type: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    old_values: Optional[str]  # JSON string
    new_values: Optional[str]  # JSON string
    metadata: Optional[str]  # JSON string
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


class AuditLogError(Exception):
    """Raised when audit log operations fail."""


def list_audit_logs(
    limit: int = 100,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None
) -> List[AuditLog]:
    """List audit logs with optional filters.
    
    Args:
        limit: Maximum number of logs to return
        user_id: Filter by user ID
        action_type: Filter by action type
        resource_type: Filter by resource type
        
    Returns:
        List of AuditLog objects
        
    Raises:
        AuditLogError: If lookup fails
    """
    connection = get_db_connection()
    
    query = """
        SELECT 
            id::text,
            user_id::text,
            action_type,
            resource_type,
            resource_id::text,
            old_values::text,
            new_values::text,
            metadata::text,
            ip_address::text,
            user_agent,
            created_at::text
        FROM audit_logs
        WHERE 1=1
    """
    
    params = []
    
    if user_id:
        query += " AND user_id = %s::uuid"
        params.append(user_id)
    
    if action_type:
        query += " AND action_type = %s"
        params.append(action_type)
    
    if resource_type:
        query += " AND resource_type = %s"
        params.append(resource_type)
    
    query += " ORDER BY created_at DESC LIMIT %s;"
    params.append(limit)
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise AuditLogError(f"Failed to list audit logs: {exc}") from exc
    finally:
        connection.close()
    
    return [
        AuditLog(
            id=record[0],
            user_id=record[1],
            action_type=record[2],
            resource_type=record[3],
            resource_id=record[4],
            old_values=record[5],
            new_values=record[6],
            metadata=record[7],
            ip_address=record[8],
            user_agent=record[9],
            created_at=record[10],
        )
        for record in records
    ]


def get_audit_log_by_id(log_id: str) -> Optional[AuditLog]:
    """Get a specific audit log by ID.
    
    Args:
        log_id: UUID of the audit log
        
    Returns:
        AuditLog object or None if not found
        
    Raises:
        AuditLogError: If lookup fails
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    id::text,
                    user_id::text,
                    action_type,
                    resource_type,
                    resource_id::text,
                    old_values::text,
                    new_values::text,
                    metadata::text,
                    ip_address::text,
                    user_agent,
                    created_at::text
                FROM audit_logs
                WHERE id = %s::uuid;
                """,
                (log_id,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise AuditLogError(f"Failed to get audit log: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        return None
    
    return AuditLog(
        id=record[0],
        user_id=record[1],
        action_type=record[2],
        resource_type=record[3],
        resource_id=record[4],
        old_values=record[5],
        new_values=record[6],
        metadata=record[7],
        ip_address=record[8],
        user_agent=record[9],
        created_at=record[10],
    )
