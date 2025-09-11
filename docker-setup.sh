#!/bin/bash
# InnerBoard-local Docker Setup Script
# Automated Docker deployment with progress tracking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}🐳 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "$1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main Docker setup function
main() {
    print_header "InnerBoard-local Docker Setup"
    echo "Setting up InnerBoard-local with Docker..."
    echo

    # Step 1: Check Docker
    print_header "Step 1: Checking Docker Installation"

    if ! command_exists docker; then
        print_error "Docker not found. Please install Docker first:"
        echo "  - Download from: https://docs.docker.com/get-docker/"
        exit 1
    fi

    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    print_success "Docker found: $DOCKER_VERSION"

    # Check Docker Compose
    if command_exists docker-compose; then
        DOCKER_COMPOSE_CMD="docker-compose"
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}')
        print_success "Docker Compose found: $COMPOSE_VERSION"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
        COMPOSE_VERSION=$(docker compose version | awk '{print $2}')
        print_success "Docker Compose (plugin) found: $COMPOSE_VERSION"
    else
        print_error "Docker Compose not found. Please install Docker Compose:"
        echo "  - Usually included with Docker Desktop"
        echo "  - Or install separately: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Step 2: Build images
    print_header "Step 2: Building Docker Images"
    print_info "This may take a few minutes..."

    if ! $DOCKER_COMPOSE_CMD build; then
        print_error "Failed to build Docker images"
        exit 1
    fi
    print_success "Docker images built successfully"

    # Step 3: Start services
    print_header "Step 3: Starting Services"
    print_info "Starting Ollama and InnerBoard services..."

    if ! $DOCKER_COMPOSE_CMD up -d; then
        print_error "Failed to start services"
        exit 1
    fi
    print_success "Services started successfully"

    # Step 4: Wait for services to be ready
    print_header "Step 4: Waiting for Services to be Ready"

    print_info "Waiting for Ollama to start..."
    max_attempts=30
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:11434/api/tags >/dev/null 2>&1; then
            print_success "Ollama is ready!"
            break
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    if [ $attempt -gt $max_attempts ]; then
        print_warning "Ollama may still be starting. Please wait a moment."
    fi

    # Step 5: Pull AI model
    print_header "Step 5: Downloading AI Model"
    print_info "Downloading gpt-oss:20b model (this may take several minutes)..."

    if ! $DOCKER_COMPOSE_CMD exec -T ollama ollama pull gpt-oss:20b; then
        print_warning "Model download may have failed. You can try again later:"
        echo "  $DOCKER_COMPOSE_CMD exec ollama ollama pull gpt-oss:20b"
    else
        print_success "AI model downloaded successfully"
    fi

    # Step 6: Initialize vault
    print_header "Step 6: Initializing InnerBoard Vault"
    print_info "Setting up encrypted vault..."

    # Create data directory if it doesn't exist
    mkdir -p data

    if ! $DOCKER_COMPOSE_CMD exec -T innerboard innerboard init --no-interactive; then
        print_warning "Vault initialization may have failed. You can initialize manually:"
        echo "  $DOCKER_COMPOSE_CMD exec innerboard innerboard init"
    else
        print_success "Vault initialized successfully"
    fi

    # Step 7: Show status
    print_header "Step 7: Checking Status"

    echo
    print_info "Service Status:"
    $DOCKER_COMPOSE_CMD ps

    echo
    print_info "InnerBoard Status:"
    $DOCKER_COMPOSE_CMD exec -T innerboard innerboard status || echo "Status check failed - services may still be starting"

    # Success!
    print_header "🎉 Docker Setup Complete!"
    echo
    print_success "InnerBoard-local is ready to use with Docker!"
    echo
    print_info "Quick Docker commands:"
    echo "  # Add a reflection"
    echo "  $DOCKER_COMPOSE_CMD exec innerboard innerboard add \"Your reflection here\""
    echo
    echo "  # List reflections"
    echo "  $DOCKER_COMPOSE_CMD exec innerboard innerboard list"
    echo
    echo "  # Generate meeting prep"
    echo "  $DOCKER_COMPOSE_CMD exec innerboard innerboard prep"
    echo
    echo "  # View logs"
    echo "  $DOCKER_COMPOSE_CMD logs -f"
    echo
    echo "  # Stop services"
    echo "  $DOCKER_COMPOSE_CMD down"
    echo
    print_info "📚 Full documentation: https://github.com/ramper-labs/InnerBoard-local"
    echo
    print_info "💡 Tip: Add these aliases to your ~/.bashrc or ~/.zshrc:"
    echo "  alias innerboard='$DOCKER_COMPOSE_CMD exec innerboard innerboard'"
}

# Run main function
main "$@"
