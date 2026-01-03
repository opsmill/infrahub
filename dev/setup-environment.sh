#!/bin/bash
# Infrahub Development Environment Setup Script
# This script sets up the development environment for the Infrahub project

set -e  # Exit on any error

# Get the project directory (parent of dev/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up Infrahub development environment..."
echo "Project directory: $PROJECT_DIR"

# Change to project root
cd "$PROJECT_DIR"

# ------------------------------------------------------------------------------
# Python Dependencies
# ------------------------------------------------------------------------------
echo ""
echo "Installing Python dependencies with uv..."
if command -v uv &> /dev/null; then
    uv sync --all-groups
    echo "Python dependencies installed"
else
    echo "Warning: uv not found. Please install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# ------------------------------------------------------------------------------
# Frontend Dependencies
# ------------------------------------------------------------------------------
echo ""
echo "Installing frontend dependencies with npm..."
if command -v npm &> /dev/null; then
    if [ -d "$PROJECT_DIR/frontend/app" ]; then
        cd "$PROJECT_DIR/frontend/app"
        npm install
        echo "Frontend dependencies installed"
        cd "$PROJECT_DIR"
    else
        echo "Warning: Frontend directory not found at $PROJECT_DIR/frontend/app"
    fi
else
    echo "Warning: npm not found. Please install Node.js first"
fi

# ------------------------------------------------------------------------------
# GitHub CLI (optional - failure won't block setup)
# ------------------------------------------------------------------------------
echo ""
echo "Installing GitHub CLI (gh)..."
if command -v gh &> /dev/null; then
    echo "GitHub CLI already installed: $(gh --version | head -n1)"
else
    # Detect package manager and install (non-fatal)
    install_gh() {
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu
            (type -p wget >/dev/null || sudo apt-get install wget -y) \
                && sudo mkdir -p -m 755 /etc/apt/keyrings \
                && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
                && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
                && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
                && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
                && sudo apt-get update \
                && sudo apt-get install gh -y
        elif command -v dnf &> /dev/null; then
            # Fedora/RHEL
            sudo dnf install 'dnf-command(config-manager)' -y \
                && sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo \
                && sudo dnf install gh -y
        elif command -v brew &> /dev/null; then
            # macOS with Homebrew
            brew install gh
        else
            echo "Warning: Could not detect package manager. Please install GitHub CLI manually:"
            echo "  https://github.com/cli/cli#installation"
            return 1
        fi
    }
    if install_gh; then
        echo "GitHub CLI installed"
    else
        echo "Warning: GitHub CLI installation failed (optional, continuing...)"
    fi
fi

# ------------------------------------------------------------------------------
# yq YAML Processor (optional - failure won't block setup)
# ------------------------------------------------------------------------------
echo ""
echo "Installing yq YAML processor..."
if command -v yq &> /dev/null; then
    echo "yq already installed: $(yq --version)"
else
    install_yq() {
        if command -v apt-get &> /dev/null; then
            sudo apt-get install yq -y 2>/dev/null || {
                # Install via binary if apt package not available
                YQ_VERSION=$(curl -s https://api.github.com/repos/mikefarah/yq/releases/latest | grep tag_name | cut -d '"' -f 4)
                sudo wget -qO /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"
                sudo chmod +x /usr/local/bin/yq
            }
        elif command -v brew &> /dev/null; then
            brew install yq
        else
            echo "Warning: Could not install yq automatically"
            return 1
        fi
    }
    if install_yq; then
        echo "yq installed"
    else
        echo "Warning: yq installation failed (optional, continuing...)"
    fi
fi

# ------------------------------------------------------------------------------
# Set Environment Variables (if ENV_FILE is provided)
# ------------------------------------------------------------------------------
if [ -n "$ENV_FILE" ]; then
    echo ""
    echo "Setting environment variables..."
    {
        echo "export INFRAHUB_PROJECT_DIR=\"$PROJECT_DIR\""
        echo "export PATH=\"$PROJECT_DIR/.venv/bin:\$PATH\""
    } >> "$ENV_FILE"
    echo "Environment variables configured"
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "Environment setup complete!"
echo "=========================================="
echo ""
echo "Available commands:"
echo "  uv run invoke backend.test-unit    - Run backend unit tests"
echo "  uv run invoke format               - Format Python code"
echo "  uv run invoke lint                 - Lint Python code"
echo "  cd frontend/app && npm run test    - Run frontend tests"
echo "  cd frontend/app && npm run biome:fix - Format/lint frontend"
echo ""

exit 0
