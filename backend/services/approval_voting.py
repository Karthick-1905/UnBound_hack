"""Approval voting service for multi-admin approval workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import psycopg2

from db.connect import get_db_connection


@dataclass(frozen=True)
class ApprovalVote:
    """Represents an approval vote from an admin."""

    id: str
    approval_request_id: str
    admin_id: str
    vote: str  # 'APPROVE' or 'REJECT'
    comment: Optional[str]
    created_at: str


class ApprovalVotingError(Exception):
    """Base exception for approval voting operations."""


class DuplicateVoteError(ApprovalVotingError):
    """Raised when admin tries to vote twice on same request."""


def cast_vote(
    approval_request_id: str,
    admin_id: str,
    vote: str,
    comment: Optional[str] = None
) -> ApprovalVote:
    """Cast an approval vote.
    
    Args:
        approval_request_id: UUID of the approval request
        admin_id: UUID of the admin voting
        vote: 'APPROVE' or 'REJECT'
        comment: Optional comment explaining the vote
        
    Returns:
        Created ApprovalVote object
        
    Raises:
        DuplicateVoteError: If admin has already voted
        ApprovalVotingError: If vote creation fails
    """
    if vote not in ('APPROVE', 'REJECT'):
        raise ApprovalVotingError(f"Invalid vote: {vote}. Must be APPROVE or REJECT")
    
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            # Insert vote
            cursor.execute(
                """
                INSERT INTO approval_votes 
                (approval_request_id, admin_id, vote, comment)
                VALUES (%s::uuid, %s::uuid, %s, %s)
                RETURNING id::text, approval_request_id::text, admin_id::text, 
                          vote, comment, created_at::text;
                """,
                (approval_request_id, admin_id, vote, comment),
            )
            record = cursor.fetchone()
            
            # Update approval request counts
            if vote == 'APPROVE':
                cursor.execute(
                    """
                    UPDATE approval_requests
                    SET current_approvals = current_approvals + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s::uuid;
                    """,
                    (approval_request_id,),
                )
            
        connection.commit()
    except psycopg2.errors.UniqueViolation as exc:
        connection.rollback()
        raise DuplicateVoteError("Admin has already voted on this request") from exc
    except psycopg2.Error as exc:
        connection.rollback()
        raise ApprovalVotingError(f"Failed to cast vote: {exc}") from exc
    finally:
        connection.close()
    
    return ApprovalVote(
        id=record[0],
        approval_request_id=record[1],
        admin_id=record[2],
        vote=record[3],
        comment=record[4],
        created_at=record[5],
    )


def get_votes_for_request(approval_request_id: str) -> List[ApprovalVote]:
    """Get all votes for an approval request.
    
    Args:
        approval_request_id: UUID of the approval request
        
    Returns:
        List of ApprovalVote objects
        
    Raises:
        ApprovalVotingError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id::text, v.approval_request_id::text, v.admin_id::text, 
                       v.vote, v.comment, v.created_at::text,
                       u.username
                FROM approval_votes v
                JOIN users u ON v.admin_id = u.id
                WHERE v.approval_request_id = %s::uuid
                ORDER BY v.created_at ASC;
                """,
                (approval_request_id,),
            )
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise ApprovalVotingError(f"Failed to get votes: {exc}") from exc
    finally:
        connection.close()
    
    return [
        ApprovalVote(
            id=record[0],
            approval_request_id=record[1],
            admin_id=record[2],
            vote=record[3],
            comment=record[4],
            created_at=record[5],
        )
        for record in records
    ]


def check_threshold_met(approval_request_id: str) -> tuple[bool, int, int]:
    """Check if approval threshold has been met.
    
    Args:
        approval_request_id: UUID of the approval request
        
    Returns:
        Tuple of (threshold_met, current_approvals, required_approvals)
        
    Raises:
        ApprovalVotingError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT current_approvals, required_approvals
                FROM approval_requests
                WHERE id = %s::uuid;
                """,
                (approval_request_id,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise ApprovalVotingError(f"Failed to check threshold: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        raise ApprovalVotingError("Approval request not found")
    
    current, required = record[0], record[1]
    return (current >= required, current, required)


def has_rejection_vote(approval_request_id: str) -> bool:
    """Check if any admin has voted to reject.
    
    Args:
        approval_request_id: UUID of the approval request
        
    Returns:
        True if any REJECT vote exists
        
    Raises:
        ApprovalVotingError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM approval_votes
                WHERE approval_request_id = %s::uuid 
                  AND vote = 'REJECT';
                """,
                (approval_request_id,),
            )
            count = cursor.fetchone()[0]
    except psycopg2.Error as exc:
        raise ApprovalVotingError(f"Failed to check rejections: {exc}") from exc
    finally:
        connection.close()
    
    return count > 0


def get_admin_vote(approval_request_id: str, admin_id: str) -> Optional[ApprovalVote]:
    """Get a specific admin's vote on a request.
    
    Args:
        approval_request_id: UUID of the approval request
        admin_id: UUID of the admin
        
    Returns:
        ApprovalVote if exists, None otherwise
        
    Raises:
        ApprovalVotingError: If query fails
    """
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, approval_request_id::text, admin_id::text, 
                       vote, comment, created_at::text
                FROM approval_votes
                WHERE approval_request_id = %s::uuid 
                  AND admin_id = %s::uuid;
                """,
                (approval_request_id, admin_id),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise ApprovalVotingError(f"Failed to get admin vote: {exc}") from exc
    finally:
        connection.close()
    
    if record is None:
        return None
    
    return ApprovalVote(
        id=record[0],
        approval_request_id=record[1],
        admin_id=record[2],
        vote=record[3],
        comment=record[4],
        created_at=record[5],
    )


def calculate_required_approvals(user_tier: str, rule_tier_thresholds: dict, rule_threshold: int) -> int:
    """Calculate required approvals based on user tier and rule settings.
    
    Args:
        user_tier: User's tier (junior, mid, senior, lead)
        rule_tier_thresholds: Rule's user tier thresholds dict
        rule_threshold: Rule's base approval threshold
        
    Returns:
        Number of required approvals
    """
    # If rule has tier-specific thresholds, use those
    if rule_tier_thresholds and user_tier in rule_tier_thresholds:
        return rule_tier_thresholds[user_tier]
    
    # Otherwise use rule's base threshold
    return rule_threshold
