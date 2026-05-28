# =============================================================================
# Mini SOC Portal - Automated Database Setup Script (PowerShell)
# =============================================================================
# Usage: .\setup_db.ps1 -Method docker
#        .\setup_db.ps1 -Method manual
# =============================================================================

param (
    [ValidateSet("docker", "manual")]
    [string]$Method = "docker"
)

$ErrorActionPreference = "Stop"

# Functions
function Write-Info {
    Write-Host "[INFO] $args" -ForegroundColor Cyan
}

function Write-Success {
    Write-Host "[✓] $args" -ForegroundColor Green
}

function Write-Error {
    Write-Host "[✗] $args" -ForegroundColor Red
}

function Write-Warning {
    Write-Host "[!] $args" -ForegroundColor Yellow
}

# Script start
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Mini SOC Portal - Database Setup Script (PowerShell)    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Warning ".env file not found"
    Write-Info "Creating .env from .env.development..."
    Copy-Item ".env.development" ".env"
    Write-Success ".env created (please review and update if needed)"
}

if ($Method -eq "docker") {
    # ==========================================================================
    # DOCKER SETUP
    # ==========================================================================
    Write-Info "Starting Docker-based database setup..."
    
    # Check Docker
    $dockerCheck = docker-compose --version 2>$null
    if (-not $?) {
        Write-Error "Docker Compose is not installed"
        Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    }
    
    Write-Success "Docker Compose found: $dockerCheck"
    
    # Stop existing services
    Write-Info "Stopping existing services..."
    docker-compose down | Out-Null
    
    # Start services
    Write-Info "Starting PostgreSQL, Redis, and services..."
    docker-compose up -d
    
    # Wait for PostgreSQL to be ready
    Write-Info "Waiting for PostgreSQL to be ready..."
    Start-Sleep -Seconds 5
    
    $retries = 30
    while ($retries -gt 0) {
        try {
            $check = docker-compose exec -T db pg_isready -U postgres 2>$null
            if ($?) {
                Write-Success "PostgreSQL is ready"
                break
            }
        } catch {
            # Continue trying
        }
        
        Write-Info "Waiting... ($retries retries left)"
        Start-Sleep -Seconds 2
        $retries--
    }
    
    if ($retries -eq 0) {
        Write-Error "PostgreSQL failed to start"
        exit 1
    }
    
    # Run migrations
    Write-Info "Running Alembic migrations..."
    docker-compose exec -T backend alembic upgrade head
    
    if ($?) {
        Write-Success "Database migrations completed"
    } else {
        Write-Error "Database migrations failed"
        exit 1
    }
    
    # Seed data
    $seedInput = Read-Host "Do you want to seed sample data? (y/n)"
    if ($seedInput -eq 'y' -or $seedInput -eq 'Y') {
        Write-Info "Seeding sample data..."
        docker-compose exec -T backend python app/scripts/seed.py
        Write-Success "Sample data seeded"
    }
    
    # Show access info
    Write-Host ""
    Write-Success "✨ Database setup completed!"
    Write-Host ""
    Write-Host "Access Points:" -ForegroundColor Cyan
    Write-Host "  Frontend:  http://localhost" -ForegroundColor Green
    Write-Host "  Backend:   http://localhost/api/v1" -ForegroundColor Green
    Write-Host "  API Docs:  http://localhost/docs" -ForegroundColor Green
    Write-Host "  DB Port:   localhost:5432" -ForegroundColor Green
    Write-Host "  Redis:     localhost:6379" -ForegroundColor Green
    Write-Host ""
    Write-Host "Check status:" -ForegroundColor Cyan
    Write-Host "  docker-compose ps" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "View logs:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs -f backend" -ForegroundColor Yellow
    Write-Host ""

} elseif ($Method -eq "manual") {
    # ==========================================================================
    # MANUAL SETUP
    # ==========================================================================
    Write-Info "Starting manual database setup..."
    
    # Check Python
    $pythonCheck = python --version 2>$null
    if (-not $?) {
        Write-Error "Python 3 is not installed"
        exit 1
    }
    
    Write-Success "Python found: $pythonCheck"
    
    # Check PostgreSQL
    $psqlCheck = psql --version 2>$null
    if (-not $?) {
        Write-Error "PostgreSQL is not installed"
        Write-Host "Install from: https://www.postgresql.org/download/"
        exit 1
    }
    
    Write-Success "PostgreSQL found: $psqlCheck"
    
    # Create venv
    if (-not (Test-Path "venv")) {
        Write-Info "Creating Python virtual environment..."
        python -m venv venv
        Write-Success "Virtual environment created"
    }
    
    # Activate venv
    Write-Info "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    Write-Success "Virtual environment activated"
    
    # Install requirements
    Write-Info "Installing Python dependencies..."
    Push-Location backend
    
    python -m pip install --upgrade pip | Out-Null
    pip install -r requirements.txt | Out-Null
    Write-Success "Dependencies installed"
    
    # Create database
    Write-Info "Creating PostgreSQL database..."
    
    # Check if database exists
    $dbExists = psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='mini_soc_dev'" 2>$null
    
    if ($dbExists -eq "1") {
        Write-Warning "Database 'mini_soc_dev' already exists"
        $dropInput = Read-Host "Drop and recreate? (y/n)"
        if ($dropInput -eq 'y' -or $dropInput -eq 'Y') {
            psql -U postgres -c "DROP DATABASE IF EXISTS mini_soc_dev;" 2>$null
            Write-Info "Old database dropped"
        } else {
            Write-Info "Using existing database"
        }
    }
    
    # Create database
    psql -U postgres -c "CREATE DATABASE mini_soc_dev;" 2>$null
    Write-Success "Database 'mini_soc_dev' is ready"
    
    # Run migrations
    Write-Info "Running Alembic migrations..."
    alembic upgrade head
    
    if ($?) {
        Write-Success "Database migrations completed"
    } else {
        Write-Error "Database migrations failed"
        exit 1
    }
    
    # Seed data
    $seedInput = Read-Host "Do you want to seed sample data? (y/n)"
    if ($seedInput -eq 'y' -or $seedInput -eq 'Y') {
        Write-Info "Seeding sample data..."
        python app/scripts/seed.py
        Write-Success "Sample data seeded"
    }
    
    Pop-Location
    
    # Show info
    Write-Host ""
    Write-Success "✨ Database setup completed!"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Start Backend (from backend folder):" -ForegroundColor Cyan
    Write-Host "     uvicorn main:app --reload" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  2. Start Frontend (from frontend folder, new terminal):" -ForegroundColor Cyan
    Write-Host "     npm install && npm run dev" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Database connection:" -ForegroundColor Cyan
    Write-Host "     psql -U postgres -d mini_soc_dev" -ForegroundColor Yellow
    Write-Host ""

} else {
    Write-Error "Unknown setup method: $Method"
    Write-Host "Usage: .\setup_db.ps1 -Method [docker|manual]"
    exit 1
}

Write-Success "Setup complete!"
Write-Host ""
