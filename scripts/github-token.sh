#!/bin/bash
# Helper script to securely store GitHub token for social-media-strategist skill

WORKSPACE_DIR="$HOME/.openclaw/workspace"
ENV_FILE="$WORKSPACE_DIR/.env"

# Create workspace directory if it doesn't exist
mkdir -p "$WORKSPACE_DIR"

# Function to store token
store_token() {
    local token="$1"
    if [ -z "$token" ]; then
        echo "Error: No token provided"
        echo "Usage: $0 store <your_github_token>"
        exit 1
    fi
    
    # Check if .env exists and update, or create new
    if [ -f "$ENV_FILE" ]; then
        # Remove existing GITHUB_TOKEN line if present
        sed -i '/^GITHUB_TOKEN=/d' "$ENV_FILE"
    fi
    
    # Append new token
    echo "GITHUB_TOKEN=$token" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"  # Secure permissions
    echo "✅ Token stored securely in $ENV_FILE"
}

# Function to load and export token
load_token() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "Error: Token not found. Run: $0 store <your_token>"
        exit 1
    fi
    
    source "$ENV_FILE"
    
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "Error: GITHUB_TOKEN not set in $ENV_FILE"
        exit 1
    fi
    
    export GITHUB_TOKEN
    echo "✅ Token loaded from $ENV_FILE"
}

# Function to run report generator with token
generate_report() {
    load_token
    
    local skill_dir="$HOME/.openclaw/skills/social-media-strategist"
    cd "$skill_dir/scripts" || exit 1
    
    echo "🚀 Generating report and pushing to GitHub..."
    python3 report_generator.py
}

# Main command router
case "$1" in
    store)
        store_token "$2"
        ;;
    load)
        load_token
        ;;
    generate)
        generate_report
        ;;
    *)
        echo "Social Media Strategist - GitHub Token Manager"
        echo ""
        echo "Usage:"
        echo "  $0 store <token>    Store GitHub token securely"
        echo "  $0 load             Load and export token to environment"
        echo "  $0 generate         Generate report and push to GitHub (uses stored token)"
        echo ""
        echo "Example:"
        echo "  $0 store ghp_xxxxxxxxxxxxx"
        echo "  $0 generate"
        exit 1
        ;;
esac
