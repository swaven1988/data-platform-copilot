# deploy/secrets/

This directory holds plaintext secret files used by `docker-compose.prod.yml`.
It is in `.gitignore` and must **never** be committed.

## Setup (first-time)

Run the provided setup script:

```bash
bash deploy/secrets/setup.sh
```

Or create files manually:

```bash
# Required
echo "your-admin-token-here"  > deploy/secrets/admin_token.txt
echo "your-viewer-token-here" > deploy/secrets/viewer_token.txt
echo "your-signing-key-here"  > deploy/secrets/signing_key.txt

# Optional — omit to use heuristic-only AI mode
echo "sk-..."                 > deploy/secrets/llm_api_key.txt
```

Tokens should be random strings of at least 32 characters.
Generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`

## Secret file → environment variable mapping

| File | Env var |
|------|---------|
| `admin_token.txt` | `COPILOT_STATIC_ADMIN_TOKEN` (via file mount) |
| `viewer_token.txt` | `COPILOT_STATIC_VIEWER_TOKEN` (via file mount) |
| `signing_key.txt` | `COPILOT_SIGNING_KEY` (via file mount) |
| `llm_api_key.txt` | `LLM_API_KEY` (via file mount, optional) |
