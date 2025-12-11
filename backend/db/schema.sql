CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    api_key VARCHAR(64) UNIQUE NOT NULL, 
    role VARCHAR(10) NOT NULL CHECK (role IN ('admin', 'member')),
    user_tier VARCHAR(20) NOT NULL DEFAULT 'junior' CHECK (user_tier IN ('junior', 'mid', 'senior', 'lead')),
    credit_balance INTEGER NOT NULL DEFAULT 100,
    notification_email VARCHAR(100),
    telegram_chat_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_api_key ON users(api_key);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_tier ON users(user_tier);

CREATE TABLE rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern TEXT NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('AUTO_ACCEPT', 'AUTO_REJECT', 'NEEDS_APPROVAL')),
    description VARCHAR(255),
    approval_threshold INTEGER DEFAULT 1 CHECK (approval_threshold >= 1),
    user_tier_thresholds JSONB DEFAULT '{"junior": 3, "mid": 2, "senior": 1, "lead": 1}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_rules_active ON rules(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_rules_action ON rules(action) WHERE action = 'NEEDS_APPROVAL';

CREATE TABLE commands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    command_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN (
        'PENDING',
        'EXECUTED',
        'REJECTED',
        'FAILED',
        'NEEDS_APPROVAL'
    )),
    matched_rule_id UUID REFERENCES rules(id),
    credits_used INTEGER DEFAULT 0,
    output TEXT,  
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_commands_user_id ON commands(user_id);
CREATE INDEX idx_commands_status ON commands(status);
CREATE INDEX idx_commands_created_at ON commands(created_at DESC);
CREATE INDEX idx_commands_user_status ON commands(user_id, status);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_action_type ON audit_logs(action_type);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);

CREATE TABLE approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command_id UUID NOT NULL REFERENCES commands(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES users(id),
    required_approvals INTEGER NOT NULL DEFAULT 1,
    current_approvals INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    rejection_reason TEXT,
    notified_at TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approval_status ON approval_requests(status);
CREATE INDEX idx_approval_requested_by ON approval_requests(requested_by);
CREATE INDEX idx_approval_command_id ON approval_requests(command_id);
CREATE INDEX idx_approval_expires_at ON approval_requests(expires_at) WHERE status = 'PENDING';

CREATE TABLE approval_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_request_id UUID NOT NULL REFERENCES approval_requests(id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES users(id),
    vote VARCHAR(10) NOT NULL CHECK (vote IN ('APPROVE', 'REJECT')),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(approval_request_id, admin_id)
);

CREATE INDEX idx_approval_votes_request ON approval_votes(approval_request_id);
CREATE INDEX idx_approval_votes_admin ON approval_votes(admin_id);

CREATE TABLE rule_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id_1 UUID NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    rule_id_2 UUID NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    conflict_type VARCHAR(50) NOT NULL,
    test_case TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rule_id_1, rule_id_2)
);

CREATE INDEX idx_rule_conflicts_rule1 ON rule_conflicts(rule_id_1);
CREATE INDEX idx_rule_conflicts_rule2 ON rule_conflicts(rule_id_2);
