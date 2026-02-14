# 1) You’re running pytest outside the venv that has deps OR your venv has no deps.
# Fix it with ONE of the below (pick pip or uv).

# --- Option A: pip (recommended) ---
python -m pip -V
python -m pip install -U pip
python -m pip install -r requirements.txt

# If you don’t have requirements.txt, install minimum to run tests:
python -m pip install "fastapi>=0.110" "starlette>=0.37" "httpx>=0.27" "pytest>=8"

# Re-run:
python -m pytest -q


# 2) Since rg isn’t installed, use grep to find the files (Git Bash).

# Find registry/fingerprint/resolve locations
grep -RIn --include="*.py" -E "fingerprint|register\(|resolve\(|Registry|plugins/resolve" app

# Find the advisor execution loop / normalize_result / advisor_findings
grep -RIn --include="*.py" -E "_normalize_result|normalize_result|advisor_findings|run_advisors|execute_advisors|AdvisorsRunConfig|phase|priority" app

# Find where routers are included (for /execution/graph)
grep -RIn --include="*.py" -E "include_router|APIRouter" app

# Also dump candidate files list (send me this output)
grep -RIl --include="*.py" -E "_normalize_result|advisor_findings|registry\.resolve|fingerprint|register\(" app
