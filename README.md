# Data Platform Copilot

An enterprise-grade GenAI Copilot for data platform engineering.

## Capabilities (Planned)
- Generate Spark (Scala / PySpark) jobs from requirements
- Generate SQL pipelines and optional Data Quality (DQ) checks
- Generate Airflow DAGs with environment-aware Spark configs
- Sync with user-modified code (drift detection + patching)
- Failure troubleshooting for Airflow, Spark, and SQL
- Validation gates (lint, parse, import checks)
- Zip-ready project packaging

## Design Principles
- DQ is optional and can be added later
- Generated code is editable by users
- Copilot reconciles changes via Sync, not guessing
- Portable and vendor-neutral (Salesforce-grade architecture)

## Project Structure
See folders under `app/`, `ui/`, and `templates/`.

## How to run (local)
```bash
make api
make ui
