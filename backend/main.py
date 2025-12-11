"""FastAPI application entrypoint for the UnBound Command Gateway backend."""

from __future__ import annotations
import uvicorn

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query

from auth import require_api_key, require_admin
from models import (
	UserCreateRequest,
	UserCreateResponse,
	UserProfileResponse,
	RuleCreateRequest,
	RuleUpdateRequest,
	RuleResponse,
	CommandSubmitRequest,
	CommandSubmitResponse,
	CommandResponse,
	AuditLogResponse,
)
from services.users import (
	UsernameAlreadyExistsError,
	UserCreationError,
	UserNotFoundError,
	UserLookupError,
	CreatedUser,
	create_user,
	get_user_by_api_key,
	get_user_by_username,
)
from services.rules import (
	RuleValidationError,
	RuleCreationError,
	RuleLookupError,
	RuleUpdateError,
	create_rule as create_rule_service,
	list_rules as list_rules_service,
	get_rule_by_id,
	update_rule as update_rule_service,
	delete_rule as delete_rule_service,
)
from services.commands import (
	InsufficientCreditsError,
	CommandExecutionError,
	CommandLookupError,
	submit_command as submit_command_service,
	list_commands as list_commands_service,
	get_command_by_id,
)
from services.audit import (
	AuditLogError,
	list_audit_logs as list_audit_logs_service,
	get_audit_log_by_id,
)


app = FastAPI(title="UnBound Command Gateway", version="0.1.0")


# User endpoints
@app.post("/users", response_model=UserCreateResponse, status_code=201)
def create_user_endpoint(payload: UserCreateRequest) -> UserCreateResponse:
	"""Create a new user and return their API key (shown only once)."""
	try:
		user_record, api_key = create_user(
			payload.username, 
			payload.email, 
			user_tier=payload.user_tier or "junior"
		)
	except UsernameAlreadyExistsError as exc:
		raise HTTPException(status_code=409, detail="Username already exists") from exc
	except UserCreationError as exc:
		raise HTTPException(status_code=500, detail="Failed to create user") from exc

	return UserCreateResponse(
		id=user_record.id,
		username=user_record.username,
		role=user_record.role,
		credit_balance=user_record.credit_balance,
		api_key=api_key,
	)


@app.get("/users/me", response_model=UserProfileResponse)
def get_current_user(user: CreatedUser = Depends(require_api_key)) -> UserProfileResponse:
	"""Get the authenticated user's profile."""
	return UserProfileResponse(
		id=user.id,
		username=user.username,
		role=user.role,
		user_tier=user.user_tier,
		credit_balance=user.credit_balance,
	)


@app.post("/users/switch", response_model=UserCreateResponse)
def switch_user_endpoint(username: str) -> UserCreateResponse:
	"""Switch to a different user by username (testing only - no password required)."""
	try:
		result = get_user_by_username(username)
		if result is None:
			raise HTTPException(status_code=404, detail="User not found")
		
		user_record, api_key = result
	except UserLookupError as exc:
		raise HTTPException(status_code=500, detail="Failed to switch user") from exc

	return UserCreateResponse(
		id=user_record.id,
		username=user_record.username,
		role=user_record.role,
		credit_balance=user_record.credit_balance,
		api_key=api_key,
	)


# Rule endpoints (admin only)
@app.get("/rules", response_model=List[RuleResponse])
def list_rules(
	active_only: bool = Query(True, description="Filter to active rules only"),
	_admin: CreatedUser = Depends(require_admin)
) -> List[RuleResponse]:
	"""List all rules (admin only)."""
	try:
		rules = list_rules_service(active_only=active_only)
	except RuleLookupError as exc:
		raise HTTPException(status_code=500, detail="Failed to list rules") from exc
	
	return [
		RuleResponse(
			id=rule.id,
			pattern=rule.pattern,
			action=rule.action,
			description=rule.description,
			approval_threshold=rule.approval_threshold,
			user_tier_thresholds=rule.user_tier_thresholds,
			created_at=rule.created_at,
			updated_at=rule.updated_at,
			is_active=rule.is_active,
		)
		for rule in rules
	]


@app.post("/rules", response_model=RuleResponse, status_code=201)
def create_rule(
	payload: RuleCreateRequest,
	_admin: CreatedUser = Depends(require_admin)
) -> RuleResponse:
	"""Create a new rule (admin only)."""
	try:
		rule = create_rule_service(
			pattern=payload.pattern,
			action=payload.action,
			description=payload.description,
			approval_threshold=payload.approval_threshold or 1,
			user_tier_thresholds=payload.user_tier_thresholds,
		)
	except RuleValidationError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	except RuleCreationError as exc:
		raise HTTPException(status_code=500, detail="Failed to create rule") from exc
	
	return RuleResponse(
		id=rule.id,
		pattern=rule.pattern,
		action=rule.action,
		description=rule.description,
		approval_threshold=rule.approval_threshold,
		user_tier_thresholds=rule.user_tier_thresholds,
		created_at=rule.created_at,
		updated_at=rule.updated_at,
		is_active=rule.is_active,
	)


@app.get("/rules/{rule_id}", response_model=RuleResponse)
def get_rule(
	rule_id: str,
	_admin: CreatedUser = Depends(require_admin)
) -> RuleResponse:
	"""Get a specific rule by ID (admin only)."""
	try:
		rule = get_rule_by_id(rule_id)
	except RuleLookupError as exc:
		raise HTTPException(status_code=500, detail="Failed to get rule") from exc
	
	if rule is None:
		raise HTTPException(status_code=404, detail="Rule not found")
	
	return RuleResponse(
		id=rule.id,
		pattern=rule.pattern,
		action=rule.action,
		description=rule.description,
		approval_threshold=rule.approval_threshold,
		user_tier_thresholds=rule.user_tier_thresholds,
		created_at=rule.created_at,
		updated_at=rule.updated_at,
		is_active=rule.is_active,
	)


@app.patch("/rules/{rule_id}", response_model=RuleResponse)
def update_rule(
	rule_id: str,
	payload: RuleUpdateRequest,
	_admin: CreatedUser = Depends(require_admin)
) -> RuleResponse:
	"""Update a rule (admin only)."""
	try:
		rule = update_rule_service(
			rule_id=rule_id,
			pattern=payload.pattern,
			action=payload.action,
			description=payload.description,
			is_active=payload.is_active,
			approval_threshold=payload.approval_threshold,
			user_tier_thresholds=payload.user_tier_thresholds,
		)
	except RuleValidationError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	except RuleUpdateError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	return RuleResponse(
		id=rule.id,
		pattern=rule.pattern,
		action=rule.action,
		description=rule.description,
		approval_threshold=rule.approval_threshold,
		user_tier_thresholds=rule.user_tier_thresholds,
		created_at=rule.created_at,
		updated_at=rule.updated_at,
		is_active=rule.is_active,
	)


@app.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
	rule_id: str,
	_admin: CreatedUser = Depends(require_admin)
) -> None:
	"""Soft delete a rule (admin only)."""
	try:
		delete_rule_service(rule_id)
	except RuleUpdateError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


# Command endpoints
@app.post("/commands", response_model=CommandSubmitResponse, status_code=201)
def submit_command(
	payload: CommandSubmitRequest,
	user: CreatedUser = Depends(require_api_key)
) -> CommandSubmitResponse:
	"""Submit a command for evaluation and execution."""
	try:
		command = submit_command_service(
			user_id=user.id,
			command_text=payload.command_text,
			username=user.username,
		)
		
		# Re-query to get updated balance
		from db.connect import get_db_connection
		
		connection = get_db_connection()
		try:
			with connection.cursor() as cursor:
				cursor.execute(
					"SELECT credit_balance FROM users WHERE id = %s::uuid;",
					(user.id,),
				)
				new_balance = cursor.fetchone()[0]
		finally:
			connection.close()
		
	except InsufficientCreditsError as exc:
		raise HTTPException(status_code=402, detail="Insufficient credits") from exc
	except CommandExecutionError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	return CommandSubmitResponse(
		command=CommandResponse(
			id=command.id,
			user_id=command.user_id,
			command_text=command.command_text,
			status=command.status,
			matched_rule_id=command.matched_rule_id,
			credits_used=command.credits_used,
			output=command.output,
			error_message=command.error_message,
			started_at=command.started_at,
			completed_at=command.completed_at,
			created_at=command.created_at,
		),
		new_credit_balance=new_balance,
	)


@app.get("/commands", response_model=List[CommandResponse])
def list_commands(
	limit: int = Query(50, ge=1, le=200, description="Maximum number of commands to return"),
	user: CreatedUser = Depends(require_api_key)
) -> List[CommandResponse]:
	"""List commands. Members see their own, admins see all."""
	try:
		if user.role == "admin":
			commands = list_commands_service(user_id=None, limit=limit)
		else:
			commands = list_commands_service(user_id=user.id, limit=limit)
	except CommandLookupError as exc:
		raise HTTPException(status_code=500, detail="Failed to list commands") from exc
	
	return [
		CommandResponse(
			id=cmd.id,
			user_id=cmd.user_id,
			command_text=cmd.command_text,
			status=cmd.status,
			matched_rule_id=cmd.matched_rule_id,
			credits_used=cmd.credits_used,
			output=cmd.output,
			error_message=cmd.error_message,
			started_at=cmd.started_at,
			completed_at=cmd.completed_at,
			created_at=cmd.created_at,
		)
		for cmd in commands
	]


@app.get("/commands/{command_id}", response_model=CommandResponse)
def get_command(
	command_id: str,
	user: CreatedUser = Depends(require_api_key)
) -> CommandResponse:
	"""Get a specific command. Members can only see their own, admins see all."""
	try:
		if user.role == "admin":
			command = get_command_by_id(command_id, user_id=None)
		else:
			command = get_command_by_id(command_id, user_id=user.id)
	except CommandLookupError as exc:
		raise HTTPException(status_code=500, detail="Failed to get command") from exc
	
	if command is None:
		raise HTTPException(status_code=404, detail="Command not found")
	
	return CommandResponse(
		id=command.id,
		user_id=command.user_id,
		command_text=command.command_text,
		status=command.status,
		matched_rule_id=command.matched_rule_id,
		credits_used=command.credits_used,
		output=command.output,
		error_message=command.error_message,
		started_at=command.started_at,
		completed_at=command.completed_at,
		created_at=command.created_at,
	)


# Audit endpoints (admin only)
@app.get("/audit", response_model=List[AuditLogResponse])
def list_audit_logs(
	limit: int = Query(100, ge=1, le=500, description="Maximum number of logs to return"),
	user_id: Optional[str] = Query(None, description="Filter by user ID"),
	action_type: Optional[str] = Query(None, description="Filter by action type"),
	resource_type: Optional[str] = Query(None, description="Filter by resource type"),
	_admin: CreatedUser = Depends(require_admin)
) -> List[AuditLogResponse]:
	"""List audit logs with filters (admin only)."""
	try:
		logs = list_audit_logs_service(
			limit=limit,
			user_id=user_id,
			action_type=action_type,
			resource_type=resource_type
		)
	except AuditLogError as exc:
		raise HTTPException(status_code=500, detail="Failed to list audit logs") from exc
	
	return [
		AuditLogResponse(
			id=log.id,
			user_id=log.user_id,
			action_type=log.action_type,
			resource_type=log.resource_type,
			resource_id=log.resource_id,
			old_values=log.old_values,
			new_values=log.new_values,
			metadata=log.metadata,
			ip_address=log.ip_address,
			user_agent=log.user_agent,
			created_at=log.created_at,
		)
		for log in logs
	]


@app.get("/audit/{log_id}", response_model=AuditLogResponse)
def get_audit_log(
	log_id: str,
	_admin: CreatedUser = Depends(require_admin)
) -> AuditLogResponse:
	"""Get a specific audit log by ID (admin only)."""
	try:
		log = get_audit_log_by_id(log_id)
	except AuditLogError as exc:
		raise HTTPException(status_code=500, detail="Failed to get audit log") from exc
	
	if log is None:
		raise HTTPException(status_code=404, detail="Audit log not found")
	
	return AuditLogResponse(
		id=log.id,
		user_id=log.user_id,
		action_type=log.action_type,
		resource_type=log.resource_type,
		resource_id=log.resource_id,
		old_values=log.old_values,
		new_values=log.new_values,
		metadata=log.metadata,
		ip_address=log.ip_address,
		user_agent=log.user_agent,
		created_at=log.created_at,
	)


# Approval endpoints
from services.approvals import (
	list_approval_requests,
	get_approval_request_by_id,
	ApprovalRequestError,
	ApprovalRequestNotFoundError,
)
from services.approval_voting import (
	cast_vote,
	get_votes_for_request,
	check_threshold_met,
	has_rejection_vote,
	get_admin_vote,
	DuplicateVoteError,
	ApprovalVotingError,
)
from services.notifications import send_approval_decision_email
from models import ApprovalRequestResponse, ApprovalVoteRequest, ApprovalVoteResponse


@app.get("/approvals", response_model=List[ApprovalRequestResponse])
def list_approvals(
	status: Optional[str] = Query(None, description="Filter by status (PENDING, APPROVED, REJECTED, EXPIRED)"),
	limit: int = Query(50, ge=1, le=200),
	_admin: CreatedUser = Depends(require_admin)
) -> List[ApprovalRequestResponse]:
	"""List approval requests (admin only)."""
	try:
		requests = list_approval_requests(status=status, limit=limit)
	except ApprovalRequestError as exc:
		raise HTTPException(status_code=500, detail="Failed to list approval requests") from exc
	
	return [
		ApprovalRequestResponse(
			id=req.id,
			command_id=req.command_id,
			requested_by=req.requested_by,
			required_approvals=req.required_approvals,
			current_approvals=req.current_approvals,
			status=req.status,
			rejection_reason=req.rejection_reason,
			notified_at=req.notified_at,
			expires_at=req.expires_at,
			created_at=req.created_at,
			updated_at=req.updated_at,
		)
		for req in requests
	]


@app.get("/approvals/{approval_id}", response_model=ApprovalRequestResponse)
def get_approval(
	approval_id: str,
	_admin: CreatedUser = Depends(require_admin)
) -> ApprovalRequestResponse:
	"""Get a specific approval request (admin only)."""
	try:
		req = get_approval_request_by_id(approval_id)
	except ApprovalRequestError as exc:
		raise HTTPException(status_code=500, detail="Failed to get approval request") from exc
	
	if req is None:
		raise HTTPException(status_code=404, detail="Approval request not found")
	
	return ApprovalRequestResponse(
		id=req.id,
		command_id=req.command_id,
		requested_by=req.requested_by,
		required_approvals=req.required_approvals,
		current_approvals=req.current_approvals,
		status=req.status,
		rejection_reason=req.rejection_reason,
		notified_at=req.notified_at,
		expires_at=req.expires_at,
		created_at=req.created_at,
		updated_at=req.updated_at,
	)


@app.post("/approvals/{approval_id}/vote", response_model=ApprovalVoteResponse)
def vote_on_approval(
	approval_id: str,
	payload: ApprovalVoteRequest,
	admin: CreatedUser = Depends(require_admin)
) -> ApprovalVoteResponse:
	"""Cast a vote on an approval request (admin only)."""
	
	# Check if admin already voted
	try:
		existing_vote = get_admin_vote(approval_id, admin.id)
		if existing_vote:
			raise HTTPException(
				status_code=409, 
				detail=f"You have already voted {existing_vote.vote} on this request"
			)
	except ApprovalVotingError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	# Get the approval request
	try:
		approval_req = get_approval_request_by_id(approval_id)
		if not approval_req:
			raise HTTPException(status_code=404, detail="Approval request not found")
		
		if approval_req.status != 'PENDING':
			raise HTTPException(
				status_code=400, 
				detail=f"Cannot vote on {approval_req.status} request"
			)
	except ApprovalRequestError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	# Cast the vote
	try:
		vote = cast_vote(
			approval_request_id=approval_id,
			admin_id=admin.id,
			vote=payload.vote,
			comment=payload.comment
		)
	except DuplicateVoteError as exc:
		raise HTTPException(status_code=409, detail=str(exc)) from exc
	except ApprovalVotingError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	# Check if we should finalize the decision
	from db.connect import get_db_connection
	connection = get_db_connection()
	
	try:
		# Check for rejections (one rejection = final rejection)
		if payload.vote == 'REJECT':
			# Update approval request to REJECTED
			with connection.cursor() as cursor:
				cursor.execute(
					"""
					UPDATE approval_requests
					SET status = 'REJECTED',
					    rejection_reason = %s,
					    updated_at = CURRENT_TIMESTAMP
					WHERE id = %s::uuid;
					""",
					(payload.comment or f"Rejected by {admin.username}", approval_id)
				)
				
				# Update command status
				cursor.execute(
					"""
					UPDATE commands
					SET status = 'REJECTED',
					    error_message = %s,
					    completed_at = CURRENT_TIMESTAMP
					WHERE id = %s::uuid;
					""",
					(f"Approval rejected by {admin.username}", approval_req.command_id)
				)
			connection.commit()
			
			# Send notification to requester
			try:
				# Get requester info
				with connection.cursor() as cursor:
					cursor.execute(
						"""
						SELECT u.notification_email, u.username, c.command_text
						FROM users u
						JOIN commands c ON c.user_id = u.id
						WHERE u.id = %s::uuid AND c.id = %s::uuid;
						""",
						(approval_req.requested_by, approval_req.command_id)
					)
					req_info = cursor.fetchone()
				
				if req_info and req_info[0]:
					send_approval_decision_email(
						to_email=req_info[0],
						command_text=req_info[2],
						approved=False,
						decided_by=admin.username,
						rejection_reason=payload.comment
					)
			except Exception as email_exc:
				print(f"Warning: Failed to send rejection email: {email_exc}")
		
		else:  # APPROVE vote
			# Check if threshold is met
			threshold_met, current, required = check_threshold_met(approval_id)
			
			if threshold_met:
				# Update approval request to APPROVED
				with connection.cursor() as cursor:
					cursor.execute(
						"""
						UPDATE approval_requests
						SET status = 'APPROVED',
						    updated_at = CURRENT_TIMESTAMP
						WHERE id = %s::uuid;
						""",
						(approval_id,)
					)
					
					# Execute the command (simulate execution)
					cursor.execute(
						"""
						SELECT command_text, user_id FROM commands WHERE id = %s::uuid;
						""",
						(approval_req.command_id,)
					)
					cmd_info = cursor.fetchone()
					command_text = cmd_info[0]
					user_id = cmd_info[1]
					
					simulated_output = f"[SIMULATED] Command '{command_text}' approved and would execute here"
					
					# Update command to EXECUTED
					cursor.execute(
						"""
						UPDATE commands
						SET status = 'EXECUTED',
						    credits_used = 1,
						    output = %s,
						    completed_at = CURRENT_TIMESTAMP
						WHERE id = %s::uuid;
						""",
						(simulated_output, approval_req.command_id)
					)
					
					# Deduct credit
					cursor.execute(
						"""
						UPDATE users
						SET credit_balance = credit_balance - 1
						WHERE id = %s::uuid;
						""",
						(user_id,)
					)
				connection.commit()
				
				# Send notification to requester
				try:
					with connection.cursor() as cursor:
						cursor.execute(
							"""
							SELECT notification_email, username FROM users WHERE id = %s::uuid;
							""",
							(approval_req.requested_by,)
						)
						req_info = cursor.fetchone()
					
					if req_info and req_info[0]:
						send_approval_decision_email(
							to_email=req_info[0],
							command_text=command_text,
							approved=True,
							decided_by=f"{current} admin(s)"
						)
				except Exception as email_exc:
					print(f"Warning: Failed to send approval email: {email_exc}")
	
	finally:
		connection.close()
	
	return ApprovalVoteResponse(
		id=vote.id,
		approval_request_id=vote.approval_request_id,
		admin_id=vote.admin_id,
		admin_username=admin.username,
		vote=vote.vote,
		comment=vote.comment,
		created_at=vote.created_at,
	)


@app.get("/approvals/{approval_id}/votes", response_model=List[ApprovalVoteResponse])
def list_approval_votes(
	approval_id: str,
	_admin: CreatedUser = Depends(require_admin)
) -> List[ApprovalVoteResponse]:
	"""List all votes for an approval request (admin only)."""
	try:
		votes = get_votes_for_request(approval_id)
	except ApprovalVotingError as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	
	# Get usernames for voters
	from db.connect import get_db_connection
	connection = get_db_connection()
	try:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT u.id::text, u.username
				FROM users u
				JOIN approval_votes v ON v.admin_id = u.id
				WHERE v.approval_request_id = %s::uuid;
				""",
				(approval_id,)
			)
			username_map = {row[0]: row[1] for row in cursor.fetchall()}
	finally:
		connection.close()
	
	return [
		ApprovalVoteResponse(
			id=vote.id,
			approval_request_id=vote.approval_request_id,
			admin_id=vote.admin_id,
			admin_username=username_map.get(vote.admin_id),
			vote=vote.vote,
			comment=vote.comment,
			created_at=vote.created_at,
		)
		for vote in votes
	]


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)