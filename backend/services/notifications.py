"""Email notification service for approval requests."""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class EmailConfig:
    """Email configuration from environment variables."""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str = "UnBound Command Gateway"


class EmailNotificationError(Exception):
    """Raised when email notification fails."""


def get_email_config() -> Optional[EmailConfig]:
    """Load email configuration from environment variables.
    
    Required env vars:
        SMTP_HOST: SMTP server hostname (e.g., smtp.gmail.com)
        SMTP_PORT: SMTP server port (e.g., 587)
        SMTP_USER: SMTP username/email
        SMTP_PASSWORD: SMTP password or app-specific password
        FROM_EMAIL: Email address to send from
    
    Returns:
        EmailConfig if all variables are set, None otherwise
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("FROM_EMAIL")
    
    if not all([smtp_host, smtp_port, smtp_user, smtp_password, from_email]):
        return None
    
    return EmailConfig(
        smtp_host=smtp_host,
        smtp_port=int(smtp_port),
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        from_email=from_email,
    )


def send_approval_request_email(
    to_emails: List[str],
    command_text: str,
    requested_by: str,
    approval_request_id: str,
    command_id: str,
) -> bool:
    """Send approval request notification email to admins.
    
    Args:
        to_emails: List of admin email addresses
        command_text: The command that needs approval
        requested_by: Username who requested the command
        approval_request_id: UUID of the approval request
        command_id: UUID of the command
        
    Returns:
        True if email sent successfully, False otherwise
        
    Raises:
        EmailNotificationError: If email configuration is missing or send fails
    """
    config = get_email_config()
    if not config:
        raise EmailNotificationError(
            "Email configuration not found. Please set SMTP_HOST, SMTP_PORT, "
            "SMTP_USER, SMTP_PASSWORD, and FROM_EMAIL environment variables."
        )
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔐 Approval Required: Command from {requested_by}"
    msg["From"] = f"{config.from_name} <{config.from_email}>"
    msg["To"] = ", ".join(to_emails)
    
    # Plain text version
    text_body = f"""
Command Approval Request
========================

A command requires your approval before execution.

Requested by: {requested_by}
Command: {command_text}

Approval Request ID: {approval_request_id}
Command ID: {command_id}

To approve or reject this command, use the CLI:
  unbound approvals_approve {approval_request_id}
  unbound approvals_reject {approval_request_id} "reason"

Or use the shell:
  approvals_approve {approval_request_id}
  approvals_reject {approval_request_id} "reason"

This request will expire in 24 hours.

---
UnBound Command Gateway
"""
    
    # HTML version
    html_body = f"""
<html>
  <head>
    <style>
      body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
      .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
      .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
      .command {{ background-color: #f1f3f5; padding: 15px; border-left: 4px solid #fbbf24; margin: 20px 0; font-family: monospace; }}
      .info {{ margin: 15px 0; }}
      .label {{ font-weight: bold; color: #495057; }}
      .actions {{ background-color: #e7f5ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
      .footer {{ color: #868e96; font-size: 12px; margin-top: 30px; }}
    </style>
  </head>
  <body>
    <div class="container">
      <div class="header">
        <h2>🔐 Command Approval Required</h2>
      </div>
      
      <div class="info">
        <p><span class="label">Requested by:</span> {requested_by}</p>
      </div>
      
      <div class="command">
        <strong>Command:</strong><br>
        {command_text}
      </div>
      
      <div class="info">
        <p><span class="label">Approval Request ID:</span> <code>{approval_request_id[:8]}...</code></p>
        <p><span class="label">Command ID:</span> <code>{command_id[:8]}...</code></p>
      </div>
      
      <div class="actions">
        <h3>How to Respond</h3>
        <p>Use the UnBound CLI to approve or reject:</p>
        <pre>approvals_approve {approval_request_id[:8]}</pre>
        <pre>approvals_reject {approval_request_id[:8]} "reason"</pre>
        <p><em>⏰ This request expires in 24 hours</em></p>
      </div>
      
      <div class="footer">
        <p>UnBound Command Gateway - Automated Notification</p>
      </div>
    </div>
  </body>
</html>
"""
    
    # Attach both versions
    part1 = MIMEText(text_body, "plain")
    part2 = MIMEText(html_body, "html")
    msg.attach(part1)
    msg.attach(part2)
    
    # Send email
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.from_email, to_emails, msg.as_string())
        return True
    except Exception as exc:
        raise EmailNotificationError(f"Failed to send email: {exc}") from exc


def send_approval_decision_email(
    to_email: str,
    command_text: str,
    approved: bool,
    decided_by: str,
    rejection_reason: Optional[str] = None,
) -> bool:
    """Send notification when approval request is approved/rejected.
    
    Args:
        to_email: Email of user who requested the command
        command_text: The command that was approved/rejected
        approved: True if approved, False if rejected
        decided_by: Admin who made the decision
        rejection_reason: Reason for rejection (if rejected)
        
    Returns:
        True if email sent successfully
        
    Raises:
        EmailNotificationError: If send fails
    """
    config = get_email_config()
    if not config:
        return False  # Silently skip if email not configured
    
    status = "Approved ✓" if approved else "Rejected ✗"
    emoji = "✅" if approved else "❌"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{emoji} Your Command Request was {status}"
    msg["From"] = f"{config.from_name} <{config.from_email}>"
    msg["To"] = to_email
    
    text_body = f"""
Command Request {status}
{'=' * 40}

Your command has been {status.lower()}.

Command: {command_text}
Decided by: {decided_by}
"""
    
    if not approved and rejection_reason:
        text_body += f"\nReason: {rejection_reason}"
    
    if approved:
        text_body += "\n\nYou can now resubmit the command for execution."
    
    text_body += "\n\n---\nUnBound Command Gateway"
    
    html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2>{emoji} Command Request {status}</h2>
    <p>Your command has been <strong>{status.lower()}</strong>.</p>
    <div style="background-color: #f1f3f5; padding: 15px; margin: 20px 0; font-family: monospace;">
      {command_text}
    </div>
    <p><strong>Decided by:</strong> {decided_by}</p>
"""
    
    if not approved and rejection_reason:
        html_body += f'<p><strong>Reason:</strong> {rejection_reason}</p>'
    
    if approved:
        html_body += '<p style="color: green;">✓ You can now resubmit the command for execution.</p>'
    
    html_body += """
    <hr>
    <p style="color: #868e96; font-size: 12px;">UnBound Command Gateway</p>
  </body>
</html>
"""
    
    part1 = MIMEText(text_body, "plain")
    part2 = MIMEText(html_body, "html")
    msg.attach(part1)
    msg.attach(part2)
    
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.from_email, [to_email], msg.as_string())
        return True
    except Exception:
        return False  # Silently fail for notifications
