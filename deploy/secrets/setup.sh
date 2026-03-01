#!/usr/bin/env bash
# Setup script for deploy/secrets/ — generates placeholder tokens for local/dev use.
# For production, replace generated values with real secrets before deploying.
set -euo pipefail

SECRETS_DIR="$(cd "$(dirname "$0")" && pwd)"

generate_token() {
    python3 -c "import secrets; print(secrets.token_hex(32))"
}

create_if_missing() {
    local file="$1"
    local value="$2"
    local label="$3"
    if [ -f "$file" ]; then
        echo "  SKIP: $label already exists at $file"
    else
        echo "$value" > "$file"
        echo "  CREATED: $label → $file"
    fi
}

echo "Setting up deploy/secrets/ ..."
create_if_missing "$SECRETS_DIR/admin_token.txt"  "$(generate_token)" "admin_token"
create_if_missing "$SECRETS_DIR/viewer_token.txt" "$(generate_token)" "viewer_token"
create_if_missing "$SECRETS_DIR/signing_key.txt"  "$(generate_token)" "signing_key"

# llm_api_key is optional
if [ -f "$SECRETS_DIR/llm_api_key.txt" ]; then
    echo "  SKIP: llm_api_key already exists"
else
    echo "" > "$SECRETS_DIR/llm_api_key.txt"
    echo "  CREATED: llm_api_key (empty — set to your API key for AI features)"
fi

echo ""
echo "Done. To use dev tokens instead, set:"
echo "  COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=true"
echo "  COPILOT_STATIC_ADMIN_TOKEN=dev_admin_token"
