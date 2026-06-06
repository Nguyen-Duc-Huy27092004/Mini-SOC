#!/bin/bash

# ==========================================
# Mini SOC Portal - Production Deployment Helper
# ==========================================
# This script helps with common deployment tasks

set -e

COMPOSE_DEV="docker-compose.yml"
COMPOSE_PROD="docker-compose.production.yml"

print_header() {
    echo "=================================="
    echo "$1"
    echo "=================================="
}

print_success() {
    echo "✅ $1"
}

print_error() {
    echo "❌ $1"
}

print_warning() {
    echo "⚠️  $1"
}

# Development commands
dev_up() {
    print_header "Starting Development Services"
    docker-compose -f $COMPOSE_DEV up -d
    print_success "Services started"
    echo "Frontend: http://localhost"
    echo "Backend: http://localhost/api/v1"
    echo "API Docs: http://localhost/docs"
}

dev_down() {
    print_header "Stopping Development Services"
    docker-compose -f $COMPOSE_DEV down
    print_success "Services stopped"
}

dev_logs() {
    print_header "Backend Logs (Follow)"
    docker-compose -f $COMPOSE_DEV logs -f backend
}

# Production commands
prod_up() {
    print_header "Starting Production Services"
    if [ ! -f ".env.production" ]; then
        print_error ".env.production file not found!"
        print_warning "Run: $0 setup-prod"
        return 1
    fi
    
    # Load environment variables from .env.production
    export $(grep -v '^#' .env.production | xargs)
    NGINX_PORT=${NGINX_PORT:-2709}
    
    # Cleanup old containers to avoid port conflicts
    print_warning "Cleaning up old containers..."
    docker-compose -f $COMPOSE_PROD down -v 2>/dev/null || true
    
    docker-compose -f $COMPOSE_PROD up -d
    print_success "Services started in production mode"
    print_warning "VERIFY: curl http://localhost:${NGINX_PORT}/api/v1/health"
}

prod_down() {
    print_header "Stopping Production Services"
    docker-compose -f $COMPOSE_PROD down
    print_success "Services stopped"
}

prod_logs() {
    print_header "Production Backend Logs (Follow)"
    docker-compose -f $COMPOSE_PROD logs -f backend
}

# Database commands
db_backup() {
    print_header "Creating Database Backup"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backup_${TIMESTAMP}.sql.gz"
    docker-compose exec db pg_dump -U postgres -d mini_soc | gzip > "${BACKUP_FILE}"
    print_success "Backup created: ${BACKUP_FILE}"
}

db_restore() {
    if [ -z "$1" ]; then
        print_error "Usage: $0 db-restore <backup_file>"
        return 1
    fi
    print_header "Restoring Database from $1"
    gunzip -c "$1" | docker-compose exec -T db psql -U postgres -d mini_soc
    print_success "Database restored"
}

# Health check
health_check() {
    print_header "Health Check"
    
    echo -n "API Health: "
    curl -s http://localhost/api/v1/health | grep -q "healthy" && print_success "OK" || print_error "FAILED"
    
    echo -n "Database: "
    docker-compose exec db pg_isready > /dev/null 2>&1 && print_success "OK" || print_error "FAILED"
    
    echo -n "Redis: "
    docker-compose exec redis redis-cli ping > /dev/null 2>&1 && print_success "OK" || print_error "FAILED"
    
    echo -n "Services Running: "
    docker-compose ps | grep -q "Up" && print_success "OK" || print_error "FAILED"
}

# Setup production
setup_prod() {
    print_header "Setting Up Production Environment"
    
    if [ -f ".env.production" ]; then
        print_warning ".env.production already exists"
        read -p "Overwrite? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    cp .env.production .env
    print_success "Created .env from .env.production"
    
    print_warning "IMPORTANT: Edit .env and change all required values:"
    print_warning "  - SECRET_KEY (generate: python -c \"import secrets; print(secrets.token_hex(32))\")"
    print_warning "  - Database password"
    print_warning "  - OpenSearch password"
    print_warning "  - BACKEND_CORS_ORIGINS (your domain)"
    print_warning "  - Admin password"
    
    echo ""
    echo "Edit .env with: nano .env"
}

# Create admin user
create_admin() {
    print_header "Creating Admin User"
    
    if ! docker-compose exec backend python -m app.scripts.create_admin_user; then
        print_error "Failed to create admin user"
        print_warning "Ensure database is running and initialized"
        return 1
    fi
    print_success "Admin user created"
}

# Show help
show_help() {
    cat << EOF
Mini SOC Portal - Production Deployment Helper

Usage: $0 <command>

Development Commands:
  dev-up              Start development services
  dev-down            Stop development services
  dev-logs            View backend logs
  dev-shell           Enter backend container shell

Production Commands:
  setup-prod          Setup production environment (.env)
  prod-up             Start production services
  prod-down           Stop production services
  prod-logs           View production backend logs

Database Commands:
  db-backup           Create database backup
  db-restore <file>   Restore from backup file

Monitoring:
  health              Health check all services
  status              Show service status

Admin:
  create-admin        Create admin user

Other:
  help                Show this help message

Examples:
  $0 dev-up
  $0 db-backup
  $0 setup-prod
  $0 prod-up

EOF
}

# Main command handling
case "${1:-help}" in
    dev-up)
        dev_up
        ;;
    dev-down)
        dev_down
        ;;
    dev-logs)
        dev_logs
        ;;
    dev-shell)
        docker-compose exec backend bash
        ;;
    setup-prod)
        setup_prod
        ;;
    prod-up)
        prod_up
        ;;
    prod-down)
        prod_down
        ;;
    prod-logs)
        prod_logs
        ;;
    db-backup)
        db_backup
        ;;
    db-restore)
        db_restore "$2"
        ;;
    health)
        health_check
        ;;
    status)
        docker-compose ps
        ;;
    create-admin)
        create_admin
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
