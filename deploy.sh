#!/bin/bash

################################################################################
#                  Phoenician Screening Engine - Deploy Script                 #
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

################################################################################
# PRE-FLIGHT CHECKS
################################################################################

log_info "Running pre-flight checks..."

# Check if .env exists
if [ ! -f .env ]; then
    log_error ".env file not found"
    log_info "Creating .env from .env.placeholder"
    cp .env.placeholder .env
    log_warning "Please edit .env with your API keys and database credentials"
    exit 1
fi

# Check docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi

# Check docker-compose
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi

log_success "All pre-flight checks passed"

################################################################################
# BUILD IMAGES
################################################################################

log_info "Building Docker images..."
docker-compose build

log_success "Docker images built successfully"

################################################################################
# START SERVICES
################################################################################

log_info "Starting services..."
docker-compose up -d

log_success "Services started"

################################################################################
# WAIT FOR HEALTH
################################################################################

log_info "Waiting for services to be healthy..."

# Wait for database
log_info "Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T db pg_isready -U phoenician &> /dev/null; then
        log_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "PostgreSQL failed to start"
        exit 1
    fi
    sleep 2
done

# Wait for Redis
log_info "Waiting for Redis..."
for i in {1..20}; do
    if docker-compose exec -T redis redis-cli ping &> /dev/null; then
        log_success "Redis is ready"
        break
    fi
    if [ $i -eq 20 ]; then
        log_error "Redis failed to start"
        exit 1
    fi
    sleep 2
done

# Wait for API
log_info "Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/v1/screening/status &> /dev/null; then
        log_success "API is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "API failed to start"
        docker-compose logs api
        exit 1
    fi
    sleep 2
done

################################################################################
# RUN MIGRATIONS
################################################################################

log_info "Running database migrations..."

# Get migration files
MIGRATION_FILES=$(ls src/db/migrations/*.sql 2>/dev/null || echo "")

if [ -z "$MIGRATION_FILES" ]; then
    log_warning "No migration files found"
else
    for migration in $(ls src/db/migrations/*.sql | sort); do
        log_info "Running: $(basename $migration)"
        docker-compose exec -T db psql -U phoenician -d phoenician < "$migration"
        log_success "Completed: $(basename $migration)"
    done
fi

log_success "All migrations completed"

################################################################################
# VERIFY DEPLOYMENT
################################################################################

log_info "Verifying deployment..."

# Test API
log_info "Testing API..."
if curl -s -f http://localhost:8000/api/v1/screening/status > /dev/null; then
    log_success "API is responding"
else
    log_error "API is not responding"
    exit 1
fi

# Test Frontend
log_info "Testing Frontend..."
if curl -s -f http://localhost:5000 > /dev/null; then
    log_success "Frontend is responding"
else
    log_error "Frontend is not responding"
fi

# Test Database
log_info "Testing Database..."
if docker-compose exec -T db psql -U phoenician -d phoenician -c "SELECT 1" &> /dev/null; then
    log_success "Database is accessible"
else
    log_error "Database is not accessible"
    exit 1
fi

################################################################################
# DEPLOYMENT COMPLETE
################################################################################

echo ""
log_success "═══════════════════════════════════════════════════════════"
log_success "   🚀 DEPLOYMENT SUCCESSFUL! 🚀"
log_success "═══════════════════════════════════════════════════════════"
echo ""

log_info "Services are running:"
echo "  🔷 Backend API:       http://localhost:8000"
echo "  🔶 Frontend:          http://localhost:5000"
echo "  🟢 PostgreSQL:        localhost:5433"
echo "  🔴 Redis:             localhost:6379"
echo ""

log_info "View logs:"
echo "  docker-compose logs -f                 # All services"
echo "  docker-compose logs -f api             # API only"
echo "  docker-compose logs -f db              # Database only"
echo ""

log_info "Useful commands:"
echo "  docker-compose ps                      # List services"
echo "  docker-compose restart api             # Restart API"
echo "  docker-compose down                    # Stop all services"
echo "  docker-compose exec db psql -U phoenician -d phoenician  # DB shell"
echo ""

log_info "Next steps:"
echo "  1. Open http://localhost:5000 in your browser"
echo "  2. Click 'Run Screening' to test the system"
echo "  3. Watch the real-time agent visualization"
echo "  4. Submit feedback to trigger learning"
echo ""

log_success "The bomb is live! 🚀"
