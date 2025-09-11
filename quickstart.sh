#!/bin/bash
# InnerBoard-local Quick Start Script
# This script helps new users get up and running quickly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}🚀 $1${NC}"
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

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Main setup function
main() {
    print_header "InnerBoard-local Quick Start"
    echo "Welcome! This script will help you set up InnerBoard-local in minutes."
    echo

    # Detect OS
    OS=$(detect_os)
    print_info "Detected OS: $OS"

    # Step 1: Check prerequisites
    print_header "Step 1: Checking Prerequisites"

    # Check Python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python found: $PYTHON_VERSION"
    elif command_exists python; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        print_success "Python found: $PYTHON_VERSION"
    else
        print_error "Python not found. Please install Python 3.8 or higher:"
        echo "  - Download from: https://python.org/downloads/"
        exit 1
    fi

    # Check if we have pip
    if command_exists pip3; then
        PIP_CMD="pip3"
        print_success "pip found"
    elif command_exists pip; then
        PIP_CMD="pip"
        print_success "pip found"
    else
        print_warning "pip not found - will install with get-pip.py"
        PIP_CMD=""
    fi

    # Check git
    if command_exists git; then
        print_success "Git found"
    else
        print_error "Git not found. Please install Git:"
        echo "  - Download from: https://git-scm.com/downloads"
        exit 1
    fi

    # Step 2: Clone repository
    print_header "Step 2: Downloading InnerBoard-local"

    if [[ -d "InnerBoard-local" ]]; then
        print_warning "InnerBoard-local directory already exists"
        read -p "Remove existing directory? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf InnerBoard-local
        else
            print_info "Using existing directory"
            cd InnerBoard-local
        fi
    fi

    if [[ ! -d "InnerBoard-local" ]]; then
        print_info "Cloning repository..."
        git clone https://github.com/ramper-labs/InnerBoard-local.git
        cd InnerBoard-local
        print_success "Repository cloned"
    fi

    # Step 3: Install Python dependencies
    print_header "Step 3: Installing Dependencies"

    cd InnerBoard-local

    # Install pip if needed
    if [[ -z "$PIP_CMD" ]]; then
        print_info "Installing pip..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python3 get-pip.py --user
        PIP_CMD="python3 -m pip"
        rm get-pip.py
        print_success "pip installed"
    fi

    # Install InnerBoard
    print_info "Installing InnerBoard-local..."
    $PIP_CMD install -e .
    print_success "InnerBoard-local installed"

    # Step 4: Setup Ollama
    print_header "Step 4: Setting up Ollama"

    if command_exists ollama; then
        print_success "Ollama already installed"
    else
        print_info "Installing Ollama..."

        case $OS in
            "macos")
                if command_exists brew; then
                    brew install ollama
                else
                    print_error "Homebrew not found. Please install Ollama manually:"
                    echo "  curl -fsSL https://ollama.com/install.sh | sh"
                    exit 1
                fi
                ;;
            "linux")
                curl -fsSL https://ollama.com/install.sh | sh
                ;;
            *)
                print_error "Automatic Ollama installation not supported for $OS"
                echo "Please visit: https://ollama.com/download"
                exit 1
                ;;
        esac
        print_success "Ollama installed"
    fi

    # Step 5: Download AI model
    print_header "Step 5: Downloading AI Model"
    print_info "This may take several minutes depending on your internet connection..."

    # Start Ollama service
    print_info "Starting Ollama service..."
    if [[ "$OS" == "macos" ]]; then
        brew services start ollama 2>/dev/null || ollama serve &
    else
        ollama serve &
    fi
    sleep 5

    # Pull model
    print_info "Downloading gpt-oss:20b model..."
    ollama pull gpt-oss:20b
    print_success "AI model downloaded"

    # Step 6: Initialize vault
    print_header "Step 6: Initializing Encrypted Vault"

    print_info "Setting up your secure vault..."
    innerboard init

    # Step 7: Verify setup
    print_header "Step 7: Verifying Setup"

    print_info "Testing installation..."
    innerboard status

    # Success!
    print_header "🎉 Setup Complete!"
    echo
    print_success "InnerBoard-local is ready to use!"
    echo
    print_info "Quick commands to get started:"
    echo "  innerboard add \"Your first reflection here\""
    echo "  innerboard list"
    echo "  innerboard prep"
    echo
    print_info "For more help:"
    echo "  innerboard --help"
    echo "  innerboard add --help"
    echo
    print_info "📚 Full documentation: https://github.com/ramper-labs/InnerBoard-local"
}

# Run main function
main "$@"
