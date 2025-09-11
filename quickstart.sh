#!/bin/bash
# InnerBoard-local Quick Start Script
# This script helps new users get up and running quickly
# Version: 2.2 - Added virtual environment support for externally managed Python

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
    print_info "Current directory: $(pwd)"
    print_info "Script running as: $(whoami)"

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
    print_info "Working directory: $(pwd)"
    print_info "Script version: 2.2"

    # Store original directory
    ORIGINAL_DIR="$(pwd)"
    print_info "Original directory: $ORIGINAL_DIR"

    # Handle existing directory
    if [[ -d "InnerBoard-local" ]]; then
        print_warning "InnerBoard-local directory already exists"

        # In non-interactive mode, just use existing directory
        if [[ ! -t 0 ]]; then
            print_info "Running non-interactively, using existing directory"
        else
            echo "Contents of current directory:"
            ls -la | head -5
            echo
            read -p "Remove existing directory? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Removing existing directory..."
                rm -rf InnerBoard-local
                print_success "Existing directory removed"
            else
                print_info "Using existing directory"
            fi
        fi
    fi

    # Clone if directory doesn't exist
    if [[ ! -d "InnerBoard-local" ]]; then
        print_info "Cloning repository from GitHub..."
        print_info "Command: git clone https://github.com/ramper-labs/InnerBoard-local.git"

        # Try git clone with verbose output
        if git clone https://github.com/ramper-labs/InnerBoard-local.git; then
            print_success "Repository cloned successfully"
        else
            print_error "Git clone failed with exit code: $?"
            print_info "Checking git and network connectivity..."
            git --version
            ping -c 1 github.com || echo "Network connectivity issue"
            exit 1
        fi
    fi

    # Double-check directory exists
    if [[ ! -d "InnerBoard-local" ]]; then
        print_error "InnerBoard-local directory still doesn't exist!"
        print_info "Current directory contents:"
        ls -la
        print_info "Checking permissions:"
        touch test_file 2>/dev/null && rm test_file && echo "Write permissions OK" || echo "No write permissions"
        exit 1
    fi

    # Change to directory with absolute path
    TARGET_DIR="$ORIGINAL_DIR/InnerBoard-local"
    print_info "Changing to: $TARGET_DIR"

    if cd "$TARGET_DIR"; then
        print_success "Successfully changed to InnerBoard-local directory"
        print_info "Now working in: $(pwd)"
    else
        print_error "Failed to cd to: $TARGET_DIR"
        print_info "Checking directory details:"
        ls -la "$ORIGINAL_DIR" | grep InnerBoard
        stat "$TARGET_DIR" 2>/dev/null || echo "Directory not accessible"
        exit 1
    fi

    # Step 3: Install Python dependencies
    print_header "Step 3: Installing Dependencies"

    # Install pip if needed
    if [[ -z "$PIP_CMD" ]]; then
        print_info "Installing pip..."
        if ! curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py; then
            print_error "Failed to download pip installer"
            exit 1
        fi
        if ! python3 get-pip.py --user; then
            print_error "Failed to install pip"
            rm -f get-pip.py
            exit 1
        fi
        PIP_CMD="python3 -m pip"
        rm get-pip.py
        print_success "pip installed"
    fi

    # Check if we need a virtual environment (for externally managed environments)
    VENV_DIR=""
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null && \
       python3 -c "import pip" 2>/dev/null; then
        # Test if we can install packages without issues
        if ! python3 -c "import sys; print('Testing pip install')" >/dev/null 2>&1 || \
           ! python3 -m pip install --dry-run --quiet pip 2>/dev/null; then
            print_warning "Detected externally managed Python environment"
            print_info "Creating virtual environment to avoid installation conflicts..."

            VENV_DIR="innerboard_venv"
            if [[ -d "$VENV_DIR" ]]; then
                print_info "Removing existing virtual environment..."
                rm -rf "$VENV_DIR"
            fi

            if ! python3 -m venv "$VENV_DIR"; then
                print_error "Failed to create virtual environment"
                print_info "You can create one manually:"
                echo "  python3 -m venv innerboard_venv"
                echo "  source innerboard_venv/bin/activate"
                echo "  pip install -e ."
                exit 1
            fi

            print_success "Virtual environment created: $VENV_DIR"

            # Activate virtual environment
            source "$VENV_DIR/bin/activate"
            print_info "Activated virtual environment"

            # Update pip in virtual environment
            python -m pip install --upgrade pip
        fi
    fi

    # Install InnerBoard
    print_info "Installing InnerBoard-local..."
    if ! python -m pip install -e .; then
        print_error "Failed to install InnerBoard-local"
        if [[ -n "$VENV_DIR" ]]; then
            print_info "Virtual environment troubleshooting:"
            echo "  source $VENV_DIR/bin/activate"
            echo "  python -m pip install -e ."
        else
            print_info "System installation troubleshooting:"
            echo "  pip install -e ."
            echo "  # Or with system override:"
            echo "  pip install --break-system-packages -e ."
        fi
        exit 1
    fi
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
                    if ! brew install ollama; then
                        print_error "Failed to install Ollama via Homebrew"
                        echo "Please install Ollama manually: curl -fsSL https://ollama.com/install.sh | sh"
                        exit 1
                    fi
                else
                    print_error "Homebrew not found. Please install Ollama manually:"
                    echo "  curl -fsSL https://ollama.com/install.sh | sh"
                    exit 1
                fi
                ;;
            "linux")
                if ! curl -fsSL https://ollama.com/install.sh | sh; then
                    print_error "Failed to install Ollama"
                    exit 1
                fi
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
    if ! ollama pull gpt-oss:20b; then
        print_warning "Failed to download AI model automatically"
        print_info "You can download it manually later:"
        echo "  ollama pull gpt-oss:20b"
        echo "  innerboard setup  # Run setup to complete initialization"
    else
        print_success "AI model downloaded"
    fi

    # Step 6: Initialize vault
    print_header "Step 6: Initializing Encrypted Vault"

    print_info "Setting up your secure vault..."
    if [[ -n "$VENV_DIR" ]]; then
        # Use virtual environment
        if ! "$VENV_DIR/bin/python" -m app.cli init --no-interactive; then
            print_warning "Vault initialization failed or requires manual setup"
            print_info "You can initialize the vault manually:"
            echo "  source $VENV_DIR/bin/activate"
            echo "  innerboard init"
        else
            print_success "Vault initialized"
        fi
    else
        # Use system installation
        if ! python -m app.cli init --no-interactive; then
            print_warning "Vault initialization failed or requires manual setup"
            print_info "You can initialize the vault manually:"
            echo "  innerboard init"
        else
            print_success "Vault initialized"
        fi
    fi

    # Step 7: Verify setup
    print_header "Step 7: Verifying Setup"

    print_info "Testing installation..."
    if [[ -n "$VENV_DIR" ]]; then
        # Use virtual environment
        if ! "$VENV_DIR/bin/python" -m app.cli status; then
            print_warning "Status check failed"
            print_info "Setup may be incomplete. You can check status manually:"
            echo "  source $VENV_DIR/bin/activate"
            echo "  innerboard status"
        fi
    else
        # Use system installation
        if ! python -m app.cli status; then
            print_warning "Status check failed"
            print_info "Setup may be incomplete. You can check status manually:"
            echo "  innerboard status"
        fi
    fi

    # Success!
    print_header "🎉 Setup Complete!"
    echo
    print_success "InnerBoard-local is ready to use!"

    if [[ -n "$VENV_DIR" ]]; then
        echo
        print_info "📍 Virtual Environment Created"
        echo "To use InnerBoard-local, activate the virtual environment:"
        echo "  source $VENV_DIR/bin/activate"
        echo
        print_info "Quick commands to get started:"
        echo "  source $VENV_DIR/bin/activate"
        echo "  innerboard add \"Your first reflection here\""
        echo "  innerboard list"
        echo "  innerboard prep"
        echo
        print_info "Or create an alias for convenience:"
        echo "  echo 'alias innerboard=\"source $VENV_DIR/bin/activate && innerboard\"' >> ~/.bashrc"
        echo "  source ~/.bashrc"
    else
        echo
        print_info "Quick commands to get started:"
        echo "  innerboard add \"Your first reflection here\""
        echo "  innerboard list"
        echo "  innerboard prep"
    fi

    echo
    print_info "For more help:"
    echo "  innerboard --help"
    echo "  innerboard add --help"
    echo
    print_info "📚 Full documentation: https://github.com/ramper-labs/InnerBoard-local"
}

# Run main function
main "$@"
