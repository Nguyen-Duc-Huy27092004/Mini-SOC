#!/bin/bash
# =============================================================================
# Mini SOC Portal - Automated Database Setup Script
# =============================================================================
# Usage: ./setup_db.sh [docker|manual]
# =============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Script start
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Mini SOC Portal - Database Setup Script                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    log_warning ".env file not found"
    log_info "Creating .env from .env.development..."
    cp .env.development .env
    log_success ".env created (please review and update if needed)"
fi

# Determine setup method
METHOD=${1:-"docker"}

if [ "$METHOD" = "docker" ]; then
    # ==========================================================================
    # DOCKER SETUP
    # ==========================================================================
    log_info "Starting Docker-based database setup..."
    
    # Check Docker
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    
    log_info "Docker version: $(docker-compose --version)"
    
    # Stop existing services
    log_info "Stopping existing services..."
    docker-compose down || true
    
    # Start services
    log_info "Starting PostgreSQL, Redis, and services..."
    docker-compose up -d
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    sleep 5
    
    RETRIES=30
    while [ $RETRIES -gt 0 ]; do
        if docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            break
        fi
        log_info "Waiting... ($RETRIES retries left)"
        sleep 2
        RETRIES=$((RETRIES - 1))
    done
    
    if [ $RETRIES -eq 0 ]; then
        log_error "PostgreSQL failed to start"
        exit 1
    fi
    
    # Run migrations
    log_info "Running Alembic migrations..."
    docker-compose exec -T backend alembic upgrade head
    
    if [ $? -eq 0 ]; then
        log_success "Database migrations completed"
    else
        log_error "Database migrations failed"
        exit 1
    fi
    
    # Seed data
    read -p "Do you want to seed sample data? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Seeding sample data..."
        docker-compose exec -T backend python app/scripts/seed.py
        log_success "Sample data seeded"
    fi
    
    # Show access info
    echo ""
    log_success "✨ Database setup completed!"
    echo ""
    echo -e "${BLUE}Access Points:${NC}"
    echo "  Frontend:  ${GREEN}http://localhost${NC}"
    echo "  Backend:   ${GREEN}http://localhost/api/v1${NC}"
    echo "  API Docs:  ${GREEN}http://localhost/docs${NC}"
    echo "  DB Port:   ${GREEN}localhost:5432${NC}"
    echo "  Redis:     ${GREEN}localhost:6379${NC}"
    echo ""
    echo -e "${BLUE}Check status:${NC}"
    echo "  ${YELLOW}docker-compose ps${NC}"
    echo ""
    echo -e "${BLUE}View logs:${NC}"
    echo "  ${YELLOW}docker-compose logs -f backend${NC}"
    echo ""

elif [ "$METHOD" = "manual" ]; then
    # ==========================================================================
    # MANUAL SETUP
    # ==========================================================================
    log_info "Starting manual database setup..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    log_success "Python version: $(python3 --version)"
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        log_error "PostgreSQL is not installed"
        echo "Install from: https://www.postgresql.org/download/"
        exit 1
    fi
    
    log_success "PostgreSQL version: $(psql --version)"
    
    # Create venv
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
        log_success "Virtual environment created"
    fi
    
    # Activate venv
    log_info "Activating virtual environment..."
    source venv/bin/activate
    log_success "Virtual environment activated"
    
    # Install requirements
    log_info "Installing Python dependencies..."
    cd backend
    pip install --upgrade pip > /dev/null
    pip install -r requirements.txt > /dev/null
    log_success "Dependencies installed"
    
    # Create database
    log_info "Creating PostgreSQL database..."
    
    # Check if database exists
    DB_EXISTS=$(psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='mini_soc_dev'" 2>/dev/null || echo "")
    
    if [ "$DB_EXISTS" = "1" ]; then
        log_warning "Database 'mini_soc_dev' already exists"
        read -p "Drop and recreate? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            psql -U postgres -c "DROP DATABASE IF EXISTS mini_soc_dev;" > /dev/null
            log_info "Old database dropped"
        else
            log_info "Using existing database"
        fi
    fi
    
    # Create database if not exists
    psql -U postgres -c "CREATE DATABASE mini_soc_dev;" > /dev/null 2>&1 || true
    log_success "Database 'mini_soc_dev' is ready"
    
    # Run migrations
    log_info "Running Alembic migrations..."
    alembic upgrade head
    
    if [ $? -eq 0 ]; then
        log_success "Database migrations completed"
    else
        log_error "Database migrations failed"
        exit 1
    fi
    
    # Seed data
    read -p "Do you want to seed sample data? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Seeding sample data..."
        python app/scripts/seed.py
        log_success "Sample data seeded"
    fi
    
    # Show info
    echo ""
    log_success "✨ Database setup completed!"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Start Backend (from backend folder):"
    echo "     ${YELLOW}uvicorn main:app --reload${NC}"
    echo ""
    echo "  2. Start Frontend (from frontend folder, new terminal):"
    echo "     ${YELLOW}npm install && npm run dev${NC}"
    echo ""
    echo -e "${BLUE}Database connection:${NC}"
    echo "  ${YELLOW}psql -U postgres -d mini_soc_dev${NC}"
    echo ""
else
    log_error "Unknown setup method: $METHOD"
    echo "Usage: ./setup_db.sh [docker|manual]"
    exit 1
fi

echo -e "${GREEN}Setup complete!${NC}"
echo ""
