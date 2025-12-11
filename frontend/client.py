"""HTTP client helpers for talking to the backend API."""

from __future__ import annotations

from typing import Tuple, List, Dict, Any, Optional

import httpx

from config import CLIConfig


class BackendError(Exception):
    """Raised when the backend returns a non-OK response."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"Backend error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _get_headers(cfg: CLIConfig) -> Dict[str, str]:
    """Build headers including API key if configured."""
    headers = {}
    if cfg.api_key:
        headers["X-API-Key"] = cfg.api_key
    return headers


def create_user(cfg: CLIConfig, username: str, email: Optional[str] = None) -> Tuple[str, str]:
    """Call backend to create a user; returns (user_id, api_key)."""

    url = f"{cfg.base_url.rstrip('/')}/users"
    payload = {"username": username}
    if email:
        payload["email"] = email
    
    resp = httpx.post(url, json=payload, timeout=10.0)
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)

    data = resp.json()
    return data["id"], data["api_key"]


def get_user_profile(cfg: CLIConfig) -> Dict[str, Any]:
    """Get the authenticated user's profile."""
    url = f"{cfg.base_url.rstrip('/')}/users/me"
    resp = httpx.get(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


# Rule API calls
def list_rules(cfg: CLIConfig, active_only: bool = True) -> List[Dict[str, Any]]:
    """List all rules (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/rules"
    params = {"active_only": active_only}
    resp = httpx.get(url, headers=_get_headers(cfg), params=params, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def create_rule(
    cfg: CLIConfig,
    pattern: str,
    action: str,
    description: Optional[str] = None,
    approval_threshold: Optional[int] = None,
    user_tier_thresholds: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """Create a new rule (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/rules"
    payload = {"pattern": pattern, "action": action}
    if description:
        payload["description"] = description
    if approval_threshold is not None:
        payload["approval_threshold"] = approval_threshold
    if user_tier_thresholds is not None:
        payload["user_tier_thresholds"] = user_tier_thresholds
    
    resp = httpx.post(url, headers=_get_headers(cfg), json=payload, timeout=10.0)
    
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def update_rule(
    cfg: CLIConfig,
    rule_id: str,
    pattern: Optional[str] = None,
    action: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Dict[str, Any]:
    """Update a rule (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/rules/{rule_id}"
    payload = {}
    
    if pattern is not None:
        payload["pattern"] = pattern
    if action is not None:
        payload["action"] = action
    if description is not None:
        payload["description"] = description
    if is_active is not None:
        payload["is_active"] = is_active
    
    resp = httpx.patch(url, headers=_get_headers(cfg), json=payload, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def delete_rule(cfg: CLIConfig, rule_id: str) -> None:
    """Delete a rule (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/rules/{rule_id}"
    resp = httpx.delete(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code not in (200, 204):
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)


# Command API calls
def submit_command(cfg: CLIConfig, command_text: str) -> Dict[str, Any]:
    """Submit a command for execution."""
    url = f"{cfg.base_url.rstrip('/')}/commands"
    payload = {"command_text": command_text}
    
    resp = httpx.post(url, headers=_get_headers(cfg), json=payload, timeout=30.0)
    
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def list_commands(cfg: CLIConfig, limit: int = 50) -> List[Dict[str, Any]]:
    """List commands (user's own or all if admin)."""
    url = f"{cfg.base_url.rstrip('/')}/commands"
    params = {"limit": limit}
    resp = httpx.get(url, headers=_get_headers(cfg), params=params, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def get_command(cfg: CLIConfig, command_id: str) -> Dict[str, Any]:
    """Get a specific command by ID."""
    url = f"{cfg.base_url.rstrip('/')}/commands/{command_id}"
    resp = httpx.get(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def switch_user(cfg: CLIConfig, username: str) -> Tuple[str, str]:
    """Switch to a different user by username (no password required - testing only).
    
    Returns:
        Tuple of (user_id, new_api_key)
    """
    url = f"{cfg.base_url.rstrip('/')}/users/switch"
    params = {"username": username}
    resp = httpx.post(url, params=params, timeout=10.0)
    
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)

    data = resp.json()
    return data["id"], data["api_key"]


# Audit API calls
def list_audit_logs(
    cfg: CLIConfig,
    limit: int = 100,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List audit logs with filters (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/audit"
    params = {"limit": limit}
    
    if user_id:
        params["user_id"] = user_id
    if action_type:
        params["action_type"] = action_type
    if resource_type:
        params["resource_type"] = resource_type
    
    resp = httpx.get(url, headers=_get_headers(cfg), params=params, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def get_audit_log(cfg: CLIConfig, log_id: str) -> Dict[str, Any]:
    """Get a specific audit log by ID (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/audit/{log_id}"
    resp = httpx.get(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


# Approval API calls
def list_approvals(cfg: CLIConfig, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List approval requests (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/approvals"
    params = {"limit": limit}
    if status:
        params["status"] = status
    
    resp = httpx.get(url, headers=_get_headers(cfg), params=params, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def get_approval(cfg: CLIConfig, approval_id: str) -> Dict[str, Any]:
    """Get a specific approval request (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/approvals/{approval_id}"
    resp = httpx.get(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def vote_on_approval(
    cfg: CLIConfig,
    approval_id: str,
    vote: str,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """Cast a vote on an approval request (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/approvals/{approval_id}/vote"
    payload = {"vote": vote}
    if comment:
        payload["comment"] = comment
    
    resp = httpx.post(url, headers=_get_headers(cfg), json=payload, timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()


def list_approval_votes(cfg: CLIConfig, approval_id: str) -> List[Dict[str, Any]]:
    """List all votes for an approval request (admin only)."""
    url = f"{cfg.base_url.rstrip('/')}/approvals/{approval_id}/votes"
    resp = httpx.get(url, headers=_get_headers(cfg), timeout=10.0)
    
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise BackendError(resp.status_code, detail)
    
    return resp.json()
