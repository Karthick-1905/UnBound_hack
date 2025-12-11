#!/bin/bash
# Setup script for UnBound Command Gateway

set -e

echo "╔════════════════════════════════════════════════════════╗"
echo "║     UnBound Command Gateway - Automated Setup          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Check if Python is available
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi
print_success "Python 3 found: $(python3 --version)"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker."
    exit 1
fi
print_success "Docker found: $(docker --version | cut -d' ' -f3)"

# Check if psql is available
if ! command -v psql &> /dev/null; then
    print_warning "PostgreSQL client (psql) not found. Attempting to continue anyway..."
    PSQL_AVAILABLE=false
else
    print_success "PostgreSQL client found"
    PSQL_AVAILABLE=true
fi

echo ""
print_info "Starting setup process..."
echo ""

# Step 1: Start PostgreSQL
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/6: Starting PostgreSQL Database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend

# Check if container already exists
if docker ps -a | grep -q unbound_postgres; then
    print_info "PostgreSQL container already exists. Stopping and removing..."
    docker stop unbound_postgres 2>/dev/null || true
    docker rm unbound_postgres 2>/dev/null || true
fi

docker compose up -d
if [ $? -eq 0 ]; then
    print_success "PostgreSQL container started"
else
    print_error "Failed to start PostgreSQL container"
    exit 1
fi

# Wait for PostgreSQL to be ready
print_info "Waiting for PostgreSQL to be ready (this may take 10-15 seconds)..."
for i in {1..15}; do
    if docker exec unbound_postgres pg_isready -U unbound_user &>/dev/null; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 15 ]; then
        print_error "PostgreSQL failed to start in time"
        exit 1
    fi
    sleep 1
done

# Step 2: Initialize database schema
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/6: Initializing Database Schema"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$PSQL_AVAILABLE" = true ]; then
    export PGPASSWORD=unbound_password
    if psql -h localhost -p 5433 -U unbound_user -d unbound_db -f db/schema.sql -q 2>/dev/null; then
        print_success "Database schema initialized via psql"
    else
        print_warning "psql failed, trying via Docker exec..."
        docker exec -i unbound_postgres psql -U unbound_user -d unbound_db < db/schema.sql
        print_success "Database schema initialized via Docker"
    fi
else
    print_info "Using Docker exec to initialize schema..."
    docker exec -i unbound_postgres psql -U unbound_user -d unbound_db < db/schema.sql
    print_success "Database schema initialized"
fi

# Step 3: Setup Python virtual environment (optional but recommended)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/6: Setting Up Python Environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -d ".venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

print_info "Activating virtual environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Step 4: Install backend dependencies
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/6: Installing Backend Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pip3 install -q -r requirements.txt
print_success "Backend dependencies installed"

# Step 5: Setup environment variables
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5/6: Setting Up Environment Variables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -f ".env" ]; then
    print_info "Creating .env file from template..."
    cat > .env << 'EOF'
# SMTP Configuration for Email Notifications
# Leave empty to disable email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
FROM_EMAIL=

# Database Configuration (matches docker-compose.yml)
DB_HOST=localhost
DB_PORT=5433
DB_NAME=unbound_db
DB_USER=unbound_user
DB_PASSWORD=unbound_password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
EOF
    print_success ".env file created"
    print_warning "Please configure SMTP settings in backend/.env for email notifications"
else
    print_info ".env file already exists"
fi

# Step 6: Install frontend dependencies
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6/6: Installing Frontend Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ../frontend
pip3 install -q -r requirements.txt
print_success "Frontend dependencies installed"

cd ..

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              ✅ Setup Complete!                         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
print_info "Next Steps:"
echo ""
echo "1️⃣  Start the backend server (in a terminal):"
echo "   ${BLUE}cd backend${NC}"
echo "   ${BLUE}source .venv/bin/activate${NC}  # Activate virtual environment"
echo "   ${BLUE}python3 main.py${NC}"
echo ""
echo "2️⃣  Initialize your user account (in a new terminal):"
echo "   ${BLUE}cd frontend${NC}"
echo "   ${BLUE}source ../backend/.venv/bin/activate${NC}  # Use same venv"
echo "   ${BLUE}python3 shell.py${NC}"
echo "   ${BLUE}init${NC}  # In the shell, run the init command"
echo ""
echo "3️⃣  Start using the interactive shell:"
echo "   ${BLUE}status${NC}        - Check your profile"
echo "   ${BLUE}rules_list${NC}    - View all rules"
echo "   ${BLUE}exec ls -la${NC}   - Execute a command"
echo "   ${BLUE}help${NC}          - See all available commands"
echo ""
print_warning "Optional: Configure email notifications in backend/.env"
echo ""
