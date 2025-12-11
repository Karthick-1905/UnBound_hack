"""Pydantic models shared across API routes."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, constr, Field

UsernameType = constr(min_length=3, max_length=50, strip_whitespace=True)
CommandTextType = constr(min_length=1, max_length=5000, strip_whitespace=True)


class UserCreateRequest(BaseModel):
    """Payload expected when creating a new user."""

    username: UsernameType
    email: Optional[str] = None
    user_tier: Optional[str] = Field(default="junior", pattern="^(junior|mid|senior|lead)$")


class UserCreateResponse(BaseModel):
    """Shape of the response returned after user creation."""

    id: str
    username: str
    role: str
    credit_balance: int
    api_key: str


class UserProfileResponse(BaseModel):
    """Response containing authenticated user profile data."""

    id: str
    username: str
    role: str
    user_tier: str
    credit_balance: int


# Rule models
class RuleCreateRequest(BaseModel):
    """Payload for creating a new rule."""

    pattern: str = Field(..., min_length=1, max_length=1000)
    action: str = Field(..., pattern="^(AUTO_ACCEPT|AUTO_REJECT|NEEDS_APPROVAL)$")
    description: Optional[str] = Field(None, max_length=255)
    approval_threshold: Optional[int] = Field(default=1, ge=1, le=10)
    user_tier_thresholds: Optional[dict] = Field(default={"junior": 3, "mid": 2, "senior": 1, "lead": 1})


class RuleUpdateRequest(BaseModel):
    """Payload for updating a rule."""

    pattern: Optional[str] = Field(None, min_length=1, max_length=1000)
    action: Optional[str] = Field(None, pattern="^(AUTO_ACCEPT|AUTO_REJECT|NEEDS_APPROVAL)$")
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    approval_threshold: Optional[int] = Field(None, ge=1, le=10)
    user_tier_thresholds: Optional[dict] = None


class RuleResponse(BaseModel):
    """Response containing rule data."""

    id: str
    pattern: str
    action: str
    description: Optional[str]
    approval_threshold: int
    user_tier_thresholds: dict
    created_at: str
    updated_at: str
    is_active: bool


# Command models
class CommandSubmitRequest(BaseModel):
    """Payload for submitting a command."""

    command_text: CommandTextType


class CommandResponse(BaseModel):
    """Response containing command data."""

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


class CommandSubmitResponse(BaseModel):
    """Response after submitting a command."""

    command: CommandResponse
    new_credit_balance: int


# Audit log models
class AuditLogResponse(BaseModel):
    """Response containing audit log data."""

    id: str
    user_id: Optional[str]
    action_type: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    old_values: Optional[str]
    new_values: Optional[str]
    metadata: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


# Approval models
class ApprovalRequestResponse(BaseModel):
    """Response containing approval request data."""

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


class ApprovalVoteRequest(BaseModel):
    """Request to cast an approval vote."""

    vote: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comment: Optional[str] = Field(None, max_length=500)


class ApprovalVoteResponse(BaseModel):
    """Response containing approval vote data."""

    id: str
    approval_request_id: str
    admin_id: str
    admin_username: Optional[str] = None
    vote: str
    comment: Optional[str]
    created_at: str
