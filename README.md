# UnBound Command Gateway


Before you begin, ensure you have the following installed:

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)

### Automated Setup

Run the setup script to install and configure everything automatically:

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
1.  Verify prerequisites (Python, Docker)
2. Start PostgreSQL container using Docker
3. Initialize database schema
4. Create Python virtual environment (backend + frontend)
5. Install all dependencies (backend + frontend)
6. Create environment configuration file

### Manual Setup (Alternative)

If you prefer to set up manually:

#### 1. Start PostgreSQL Database

```bash
cd backend
docker compose up -d
```

This starts PostgreSQL on port **5433** with:
- Database: `unbound_db`
- User: `unbound_user`
- Password: `unbound_password`

#### 2. Initialize Database Schema

```bash
cd backend
export PGPASSWORD=unbound_password
psql -h localhost -p 5433 -U unbound_user -d unbound_db -f db/schema.sql
```

Or using Docker:
```bash
docker exec -i unbound_postgres psql -U unbound_user -d unbound_db < db/schema.sql
```

#### 3. Setup Python Environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 4. Configure Environment Variables

Create `backend/.env`:
```bash
# SMTP Configuration (optional - for email notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@unbound.local

# Database Configuration
DB_HOST=localhost
DB_PORT=5433
DB_NAME=unbound_db
DB_USER=unbound_user
DB_PASSWORD=unbound_password
```

#### 5. Install Frontend Dependencies

```bash
cd ../frontend
pip install -r requirements.txt
```

---

## 🎯 Usage

### Starting the Backend Server

```bash
cd backend
source .venv/bin/activate  # Activate virtual environment
python3 main.py
```

The API server will start on `http://localhost:8000`

You can verify it's running by visiting:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Using the Interactive Shell (Recommended)

The interactive shell provides the best user experience with command history, auto-completion, and rich formatting.

```bash
cd frontend
source ../backend/.venv/bin/activate  # Use same virtual environment
python3 shell.py
```

#### First-Time Setup: Initialize Your Account

When you first start the shell, you need to create a user account:

```
unbound> init
```

You'll be prompted for:
- **Username**: Your desired username
- **Email**: Your email address (for notifications)

**Note**: The first user created automatically becomes an **admin**.

#### Available Commands

Once initialized, you can use these commands:

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Show your profile and credits | `status` |
| `exec <command>` | Execute a shell command | `exec ls -la` |
| `rules_list` | List all rules (admin only) | `rules_list` |
| `rules_add` | Add a new rule (admin only) | `rules_add "^rm" BLOCK "Prevent deletions"` |
| `rules_update` | Update an existing rule (admin only) | `rules_update abc-123 --action ALLOW` |
| `rules_delete` | Delete a rule (admin only) | `rules_delete abc-123` |
| `history [limit]` | Show command execution history | `history 10` |
| `cmd_info <id>` | Get details about a command | `cmd_info cmd_456` |
| `audit_list` | View audit logs (admin only) | `audit_list` |
| `refresh` | Refresh your profile | `refresh` |
| `switch <username>` | Switch to different user | `switch john` |
| `clear` | Clear screen | `clear` |
| `help` | Show all commands | `help` |
| `exit` or `quit` | Exit the shell | `exit` |

#### Command Shortcuts

| Shortcut | Full Command |
|----------|--------------|
| `s` | `status` |
| `e` | `exec` |
| `r` | `rules_list` |
| `ra` | `rules_add` |
| `ru` | `rules_update` |
| `rd` | `rules_delete` |
| `h` | `history` |

### Example Workflow

```bash
# 1. Check your status
unbound> status

# 2. View existing rules (admin only)
unbound> rules_list

# 3. Add a new rule to block dangerous commands (admin only)
unbound> rules_add "^rm -rf /" BLOCK "Prevent root deletion"

# 4. Execute a safe command
unbound> exec ls -la

# 5. Try to execute a blocked command
unbound> exec rm -rf /tmp/test

# 6. View command history
unbound> history 5

# 7. Update a rule to change its status (admin only)
unbound> rules_update abc-123 --active false

# 8. View audit logs (admin only)
unbound> audit_list
```

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    UnBound Command Gateway                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   Frontend   │────────▶│   Backend    │                 │
│  │  (CLI Shell) │◀────────│  (FastAPI)   │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                   │                          │
│                          ┌────────▼────────┐                │
│                          │   PostgreSQL    │                │
│                          │    Database     │                │
│                          └─────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

**Core Tables:**
- `users` - User accounts with roles (admin/user)
- `rules` - Pattern-based command rules
- `commands` - Command execution history
- `audit_logs` - Comprehensive audit trail
- `approval_requests` - Pending approval workflow
- `rule_conflicts` - Rule conflict detection results

### Rule Actions

| Action | Description |
|--------|-------------|
| `ALLOW` | Automatically approve and execute |
| `BLOCK` | Reject command execution |
| `NEEDS_APPROVAL` | Require admin approval before execution |

---

## 🔧 Configuration

### Environment Variables

Create `backend/.env` with these settings:

```bash
# SMTP Configuration (for email notifications)
SMTP_HOST=smtp.gmail.com          # SMTP server address
SMTP_PORT=587                      # SMTP port (587 for TLS, 465 for SSL)
SMTP_USER=your-email@gmail.com    # SMTP username
SMTP_PASSWORD=your-app-password    # SMTP password or app-specific password
FROM_EMAIL=noreply@unbound.local  # Sender email address

# Database Configuration
DB_HOST=localhost
DB_PORT=5433
DB_NAME=unbound_db
DB_USER=unbound_user
DB_PASSWORD=unbound_password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### Gmail SMTP Setup

To use Gmail for notifications:

1. Enable 2-Factor Authentication on your Google account
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Use the app password in `SMTP_PASSWORD`

---
### Database Management

**Reset Database:**
```bash
cd backend
source .venv/bin/activate
python reset_db.py
```

**View Database:**
```bash
docker exec -it unbound_postgres psql -U unbound_user -d unbound_db
```

---

## 📝 Admin Features

### Rule Management

Admins can create, update, and delete rules to control command execution

### Note : There is a Auto Completeion Features for Id,  use tab for that

```bash
# Add a rule
rules_add "^git push" NEEDS_APPROVAL "Require approval for git push"

# Update a rule's action
rules_update rule-id --action BLOCK

# Update multiple properties
rules_update rule-id --pattern "^rm" --action BLOCK --description "Block deletions"

# Toggle rule status
rules_update rule-id --active false

# Delete a rule
rules_delete rule-id
```

### Approval Workflow

When a command requires approval:

1. User submits command
2. System creates approval request
3. Admins receive email notification
4. Admin approves/rejects via CLI
5. User gets notification of decision

```bash
# List pending approvals
approvals_list

# Approve a request
approvals_approve request-id

# Reject a request
approvals_reject request-id "Reason for rejection"
```

### Audit Logs

View comprehensive audit trail:

```bash
# List all audit logs
audit_list

# View specific log entry
audit_log log-id
```

---

## 🐛 Troubleshooting

### PostgreSQL Connection Issues

**Error**: `psql: error: connection to server at "localhost" (::1), port 5433 failed`

**Solution**:
```bash
# Check if container is running
docker ps | grep unbound_postgres

# Restart container
docker restart unbound_postgres

# Check logs
docker logs unbound_postgres
```

### API Key Not Working

**Error**: `401 Unauthorized`

**Solution**:
```bash
# Re-initialize your account
cd frontend
python3 shell.py
init
```

The API key is stored in `~/.unbound_cli.json`

### Virtual Environment Issues

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Ensure virtual environment is activated
cd backend
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## 📚 API Documentation

Once the backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

### Manage Rules (Admin Only)

**List all rules:**
```bash
python main.py rules list
```

**Add a new rule:**
```bash
python main.py rules add "^sudo" AUTO_REJECT --description "Block sudo commands"
```

**Delete a rule:**
```bash
python main.py rules delete <rule-id>
```

### Submit and Manage Commands

**Submit a command:**
```bash
python main.py commands submit "ls -la"
python main.py commands submit "rm -rf /"
python main.py commands submit "git status"
```

**List recent commands:**
```bash
python main.py commands list
```

**Get command details:**
```bash
python main.py commands get <command-id>
```

## Default Rules

The system comes pre-seeded with these rules:

| Pattern | Action | Description |
|---------|--------|-------------|
| `:(){ :\|:& };:` | AUTO_REJECT | Block fork bomb |
| `rm\s+-rf\s+/` | AUTO_REJECT | Block recursive root deletion |
| `mkfs\.` | AUTO_REJECT | Block filesystem formatting |
| `git\s+(status\|log\|diff)` | AUTO_ACCEPT | Allow safe git read commands |
| `^(ls\|cat\|pwd\|echo)` | AUTO_ACCEPT | Allow basic read-only commands |

## How It Works

1. **Authentication**: Each user has an API key stored in `~/.unbound/config.json`
2. **Credit System**: Users start with 100 credits. Each executed command costs 1 credit
3. **Rule Matching**: When you submit a command:
   - System checks your credit balance (must be > 0)
   - Command is matched against rules (first match wins)
   - Based on rule action:
     - **AUTO_ACCEPT**: Command executes (simulated), credits deducted
     - **AUTO_REJECT**: Command rejected, no credits deducted
     - **NEEDS_APPROVAL**: Command pending, no credits deducted
4. **Audit Trail**: All actions are logged to the `audit_logs` table

## API Endpoints

- `POST /users` - Create a user
- `GET /users/me` - Get current user profile
- `GET /rules` - List rules (admin)
- `POST /rules` - Create rule (admin)
- `PATCH /rules/{id}` - Update rule (admin)
- `DELETE /rules/{id}` - Delete rule (admin)
- `POST /commands` - Submit command
- `GET /commands` - List commands
- `GET /commands/{id}` - Get command details

## Testing Different Scenarios

### Test as Admin
```bash
# Create admin (first user)
python main.py init --username admin

# Add custom rules
python main.py rules add "^docker" AUTO_REJECT --description "Block docker commands"

# Submit commands
python main.py commands submit "ls -la"  # Should execute (matches AUTO_ACCEPT rule)
python main.py commands submit "rm -rf /" # Should be rejected
python main.py commands submit "docker ps" # Should be rejected (if you added the rule)
```

### Test as Member
```bash
# Create a second user (will be member)
python main.py init --username member --force

# Member can submit commands but not manage rules
python main.py commands submit "cat /etc/passwd"
python main.py commands list

# This will fail (admin only)
python main.py rules list
```

## Architecture

```
backend/
├── main.py              # FastAPI app with all routes
├── auth.py              # Authentication & authorization
├── models.py            # Pydantic request/response models
├── services/
│   ├── users.py         # User management
│   ├── rules.py         # Rule CRUD and matching
│   └── commands.py      # Command execution and credits
├── db/
│   ├── connect.py       # Database connection
│   └── schema.sql       # Database schema
└── seed_rules.py        # Seed default rules

frontend/
├── main.py              # Typer CLI application
├── client.py            # HTTP client for backend API
└── config.py            # CLI configuration management
```

## Troubleshooting

**Database connection issues:**
- Ensure Docker container is running: `docker compose ps`
- Check connection settings in `backend/db/connect.py`

**CLI not authenticated:**
- Run `python main.py init` to create/configure user
- Check `~/.unbound/config.json` exists

**Backend errors:**
- Check backend logs
- Ensure database schema is applied
- Verify all dependencies are installed
