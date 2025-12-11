"""Approval requests service layer for managing command approvals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import psycopg2

from db.connect import get_db_connection


@dataclass(frozen=True)
class ApprovalRequest:
    """Represents an approval request record."""

    id: str
    command_id: str
    requested_by: str
    required_approvals: int
    current_approvals: int
    status: str
    rejection_reason: Optional[str]
    notified_at: Optional[str]
    expires_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ApprovalVote:
    """Represents an approval vote from an admin."""

    id: str
    approval_request_id: str
    admin_id: str
    vote: str  # 'APPROVE' or 'REJECT'
    comment: Optional[str]
    created_at: str


class ApprovalRequestError(Exception):
    """Base exception for approval request operations."""


class ApprovalRequestNotFoundError(ApprovalRequestError):
    """Raised when approval request not found."""


class ApprovalRequestExpiredError(ApprovalRequestError):
    """Raised when approval request has expired."""


class InvalidApprovalActionError(ApprovalRequestError):
    """Raised when trying to approve/reject an already processed request."""


def create_approval_request(
    command_id: str, 
    requested_by: str,
    required_approvals: int = 1
) -> ApprovalRequest:
    """Create a new approval request for a command.
    
    Args:
        command_id: UUID of the command needing approval
        requested_by: UUID of the user who submitted the command
        required_approvals: Number of admin approvals required
        
    Returns:
        Created ApprovalRequest object
        
    Raises:
        ApprovalRequestError: If creation fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO approval_requests 
                (command_id, requested_by, required_approvals, status)
                VALUES (%s::uuid, %s::uuid, %s, 'PENDING')
                RETURNING id::text, command_id::text, requested_by::text, required_approvals,
                          current_approvals, status, rejection_reason, 
                          notified_at::text, expires_at::text, created_at::text, updated_at::text;
                """,
                (command_id, requested_by, required_approvals),
            )
            record = cursor.fetchone()
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise ApprovalRequestError(f"Failed to create approval request: {exc}") from exc
    finally:
        connection.close()
    
    return ApprovalRequest(
        id=record[0],
        command_id=record[1],
        requested_by=record[2],
        required_approvals=record[3],
        current_approvals=record[4],
        status=record[5],
        rejection_reason=record[6],
        notified_at=record[7],
        expires_at=record[8],
        created_at=record[9],
        updated_at=record[10],
    )


def mark_notified(approval_request_id: str) -> None:
    """Mark approval request as notified.
    
    Args:
        approval_request_id: UUID of the approval request
        
    Raises:
        ApprovalRequestError: If update fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE approval_requests
                SET notified_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid;
                """,
                (approval_request_id,),
            )
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise ApprovalRequestError(f"Failed to mark as notified: {exc}") from exc
    finally:
        connection.close()


def list_approval_requests(
    status: Optional[str] = None,
    requested_by: Optional[str] = None,
    limit: int = 50
) -> List[ApprovalRequest]:
    """List approval requests with optional filtering.
    
    Args:
        status: Filter by status (PENDING, APPROVED, REJECTED, EXPIRED)
        requested_by: Filter by user ID
        limit: Maximum number of results
        
    Returns:
        List of ApprovalRequest objects
        
    Raises:
        ApprovalRequestError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT id::text, command_id::text, requested_by::text, required_approvals,
                       current_approvals, status, rejection_reason, 
                       notified_at::text, expires_at::text, created_at::text, updated_at::text
                FROM approval_requests
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            if requested_by:
                query += " AND requested_by = %s::uuid"
                params.append(requested_by)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise ApprovalRequestError(f"Failed to list approval requests: {exc}") from exc
    finally:
        connection.close()
    
    return [
        ApprovalRequest(
            id=record[0],
            command_id=record[1],
            requested_by=record[2],
            required_approvals=record[3],
            current_approvals=record[4],
            status=record[5],
            rejection_reason=record[6],
            notified_at=record[7],
            expires_at=record[8],
            created_at=record[9],
            updated_at=record[10],
        )
        for record in records
    ]


def get_approval_request_by_id(approval_request_id: str) -> Optional[ApprovalRequest]:
    """Get approval request by ID.
    
    Args:
        approval_request_id: UUID of the approval request
        
    Returns:
        ApprovalRequest object or None if not found
        
    Raises:
        ApprovalRequestError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, command_id::text, requested_by::text, required_approvals,
                       current_approvals, status, rejection_reason, 
                       notified_at::text, expires_at::text, created_at::text, updated_at::text
                FROM approval_requests
                WHERE id = %s::uuid;
                """,
                (approval_request_id,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise ApprovalRequestError(f"Failed to get approval request: {exc}") from exc
    finally:
        connection.close()
    
    if not record:
        return None
    
    return ApprovalRequest(
        id=record[0],
        command_id=record[1],
        requested_by=record[2],
        required_approvals=record[3],
        current_approvals=record[4],
        status=record[5],
        rejection_reason=record[6],
        notified_at=record[7],
        expires_at=record[8],
        created_at=record[9],
        updated_at=record[10],
    )


def approve_request(approval_request_id: str, approved_by: str) -> ApprovalRequest:
    """Approve an approval request.
    
    Args:
        approval_request_id: UUID of the approval request
        approved_by: UUID of the admin approving the request
        
    Returns:
        Updated ApprovalRequest object
        
    Raises:
        ApprovalRequestNotFoundError: If request not found
        ApprovalRequestExpiredError: If request has expired
        InvalidApprovalActionError: If request already processed
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            # Check current status
            cursor.execute(
                """
                SELECT status, expires_at
                FROM approval_requests
                WHERE id = %s::uuid;
                """,
                (approval_request_id,),
            )
            result = cursor.fetchone()
            
            if not result:
                raise ApprovalRequestNotFoundError("Approval request not found")
            
            current_status, expires_at = result
            
            if current_status != "PENDING":
                raise InvalidApprovalActionError(
                    f"Cannot approve request with status {current_status}"
                )
            
            # Check if expired
            if datetime.now() > expires_at:
                cursor.execute(
                    "UPDATE approval_requests SET status = 'EXPIRED' WHERE id = %s::uuid;",
                    (approval_request_id,),
                )
                connection.commit()
                raise ApprovalRequestExpiredError("Approval request has expired")
            
            # Approve the request
            cursor.execute(
                """
                UPDATE approval_requests
                SET status = 'APPROVED',
                    approved_by = %s::uuid,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING id::text, command_id::text, requested_by::text, status,
                          approved_by::text, approved_at::text, rejection_reason, 
                          notified_at::text, expires_at::text, created_at::text, updated_at::text;
                """,
                (approved_by, approval_request_id),
            )
            record = cursor.fetchone()
        connection.commit()
    except (ApprovalRequestNotFoundError, ApprovalRequestExpiredError, InvalidApprovalActionError):
        connection.rollback()
        connection.close()
        raise
    except psycopg2.Error as exc:
        connection.rollback()
        connection.close()
        raise ApprovalRequestError(f"Failed to approve request: {exc}") from exc
    finally:
        if connection:
            connection.close()
    
    return ApprovalRequest(
        id=record[0],
        command_id=record[1],
        requested_by=record[2],
        status=record[3],
        approved_by=record[4],
        approved_at=record[5],
        rejection_reason=record[6],
        notified_at=record[7],
        expires_at=record[8],
        created_at=record[9],
        updated_at=record[10],
    )


def reject_request(
    approval_request_id: str,
    rejected_by: str,
    reason: Optional[str] = None
) -> ApprovalRequest:
    """Reject an approval request.
    
    Args:
        approval_request_id: UUID of the approval request
        rejected_by: UUID of the admin rejecting the request
        reason: Optional reason for rejection
        
    Returns:
        Updated ApprovalRequest object
        
    Raises:
        ApprovalRequestNotFoundError: If request not found
        InvalidApprovalActionError: If request already processed
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            # Check current status
            cursor.execute(
                "SELECT status FROM approval_requests WHERE id = %s::uuid;",
                (approval_request_id,),
            )
            result = cursor.fetchone()
            
            if not result:
                raise ApprovalRequestNotFoundError("Approval request not found")
            
            current_status = result[0]
            
            if current_status != "PENDING":
                raise InvalidApprovalActionError(
                    f"Cannot reject request with status {current_status}"
                )
            
            # Reject the request
            cursor.execute(
                """
                UPDATE approval_requests
                SET status = 'REJECTED',
                    approved_by = %s::uuid,
                    approved_at = CURRENT_TIMESTAMP,
                    rejection_reason = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING id::text, command_id::text, requested_by::text, status,
                          approved_by::text, approved_at::text, rejection_reason, 
                          notified_at::text, expires_at::text, created_at::text, updated_at::text;
                """,
                (rejected_by, reason, approval_request_id),
            )
            record = cursor.fetchone()
        connection.commit()
    except (ApprovalRequestNotFoundError, InvalidApprovalActionError):
        connection.rollback()
        connection.close()
        raise
    except psycopg2.Error as exc:
        connection.rollback()
        connection.close()
        raise ApprovalRequestError(f"Failed to reject request: {exc}") from exc
    finally:
        if connection:
            connection.close()
    
    return ApprovalRequest(
        id=record[0],
        command_id=record[1],
        requested_by=record[2],
        status=record[3],
        approved_by=record[4],
        approved_at=record[5],
        rejection_reason=record[6],
        notified_at=record[7],
        expires_at=record[8],
        created_at=record[9],
        updated_at=record[10],
    )


def get_pending_approval_for_command(command_id: str, requested_by: str) -> Optional[ApprovalRequest]:
    """Check if there's a pending or approved approval request for a command.
    
    Args:
        command_id: UUID of the command
        requested_by: UUID of the user
        
    Returns:
        ApprovalRequest if found, None otherwise
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, command_id::text, requested_by::text, status,
                       approved_by::text, approved_at::text, rejection_reason, 
                       notified_at::text, expires_at::text, created_at::text, updated_at::text
                FROM approval_requests
                WHERE command_id = %s::uuid 
                  AND requested_by = %s::uuid
                  AND status IN ('PENDING', 'APPROVED')
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (command_id, requested_by),
            )
            record = cursor.fetchone()
    finally:
        connection.close()
    
    if not record:
        return None
    
    return ApprovalRequest(
        id=record[0],
        command_id=record[1],
        requested_by=record[2],
        status=record[3],
        approved_by=record[4],
        approved_at=record[5],
        rejection_reason=record[6],
        notified_at=record[7],
        expires_at=record[8],
        created_at=record[9],
        updated_at=record[10],
    )
