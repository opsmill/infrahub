#!/usr/bin/env bash
# Infrahub Development Environment Setup Script
# This script sets up the development environment for the Infrahub project

set -e  # Exit on any error

# ------------------------------------------------------------------------------
# Environment Detection
# ------------------------------------------------------------------------------
# Detect the current execution environment
# Returns: "claude-code-web", "ci", or "local"
detect_environment() {
    # Claude Code on the web sets CLAUDE_ENV_FILE for session hooks
    if [ -n "$CLAUDE_ENV_FILE" ]; then
        echo "claude-code-web"
        return
    fi

    # GitHub Actions
    if [ -n "$GITHUB_ACTIONS" ]; then
        echo "ci-github"
        return
    fi

    # GitLab CI
    if [ -n "$GITLAB_CI" ]; then
        echo "ci-gitlab"
        return
    fi

    # Add additional environment checks here as needed
    # Example:
    # if [ -n "$SOME_OTHER_ENV_VAR" ]; then
    #     echo "some-other-environment"
    #     return
    # fi

    echo "local"
}

# List of environments where this script should run
# Add new environments to this list as needed
SUPPORTED_ENVIRONMENTS="claude-code-web"

CURRENT_ENV=$(detect_environment)

# Check if current environment is supported
is_supported_environment() {
    for env in $SUPPORTED_ENVIRONMENTS; do
        if [ "$CURRENT_ENV" = "$env" ]; then
            return 0
        fi
    done
    return 1
}

if ! is_supported_environment; then
    echo "Skipping environment setup (running in '$CURRENT_ENV', supported: $SUPPORTED_ENVIRONMENTS)"
    exit 0
fi

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------
# Get the project directory (parent of dev/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up Infrahub development environment..."
echo "Environment: $CURRENT_ENV"
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
    install_gh() {
        # Download binary directly from GitHub releases
        if ! command -v curl &> /dev/null; then
            echo "Warning: curl not found, cannot install GitHub CLI"
            return 1
        fi
        GH_VERSION=$(curl -sL https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name"' | cut -d'"' -f4 | sed 's/^v//')
        if [ -z "$GH_VERSION" ]; then
            echo "Warning: Could not determine GitHub CLI version"
            return 1
        fi
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64) ARCH="amd64" ;;
            aarch64|arm64) ARCH="arm64" ;;
        esac
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        GH_TARBALL="gh_${GH_VERSION}_${OS}_${ARCH}.tar.gz"
        GH_DIR="gh_${GH_VERSION}_${OS}_${ARCH}"
        trap "rm -rf '$GH_DIR' '$GH_TARBALL'" RETURN
        curl -sLO "https://github.com/cli/cli/releases/download/v${GH_VERSION}/${GH_TARBALL}" \
            && tar -xzf "$GH_TARBALL" \
            && sudo mv "$GH_DIR/bin/gh" /usr/local/bin/
    }
    if install_gh; then
        echo "GitHub CLI installed"
    else
        echo "Warning: GitHub CLI installation failed (optional, continuing...)"
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
