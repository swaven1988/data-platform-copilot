# 🚀 Data Platform Copilot

> An enterprise-grade GenAI Copilot for Data Platform Engineering.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-API-green)]()
[![Pytest](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![Architecture](https://img.shields.io/badge/architecture-modular-orange)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

---

## 🎯 Vision

Data Platform Copilot is a modular, production-ready AI system that converts natural-language requirements into structured data pipelines — complete with:

- Spark Jobs (PySpark / Scala)
- Airflow DAGs
- Spark configurations
- Build plans
- Advisor validations
- Policy enforcement
- Intelligent risk analysis

It is designed for extensibility, reproducibility, and governance-first engineering.

---

## 🧠 Core Capabilities

- Generate Spark (Scala / PySpark) jobs from requirements
- Generate SQL pipelines with optional Data Quality (DQ) checks
- Generate Airflow DAGs with environment-aware Spark configs
- Intent-driven build engine (Requirement → Plan → Execution)
- Advisor plugin registry with dependency graph
- Policy engine with WARN / BLOCK semantics
- Drift detection and sync support
- Validation gates (lint, parse, import checks)
- Zip-ready project packaging
- Intelligence layer for risk scoring and recommendations

---

## 🏗 Architecture Overview

The system follows a layered, modular architecture:

User / API Layer (FastAPI + UI)
│
▼
Intent Parser (Requirement → Spec)
│
▼
Build Planner (Plan + Steps)
│
├──────────────┬───────────────┐
▼ ▼ ▼
Advisors Policy Engine Intelligence
(Plugins) (WARN/BLOCK) (Risk Engine)
│ │ │
└──────────────┴───────────────┘
│
▼
Plan Runner (Materialization)
│
▼
Workspace + Git (Versioned Output)

---

## 🔌 Plugin System

The advisor framework supports:

- Phase ordering (preflight / build / advise / post)
- Priority resolution
- Dependency graph execution
- Result normalization
- Run-level caching

This allows new intelligence to be added without modifying the core engine.

---

## 🛡 Policy Engine

Policies evaluate build context and return:

- `PASS`
- `WARN`
- `BLOCK`

Blocking policies prevent builds.  
Warning policies annotate builds without stopping execution.

---

## 🧪 Testing & Quality

- Full pytest coverage for:
  - Planner
  - Advisor registry
  - Policy engine
  - Build intent flow
  - Intelligence integration
- Deterministic plugin fingerprinting
- Baseline tagging for reproducibility

---

## 📦 Build Modes

| Mode       | Description |
|------------|------------|
| Dry Run    | Parse + validate + advisor analysis only |
| Plan Only  | Create build plan without materialization |
| Full Build | Generate files, run advisors, apply policy, persist plan |

---

## 🔄 Design Principles

- Vendor-neutral architecture
- DQ is optional and composable
- Generated code is fully editable
- Sync engine reconciles changes safely
- Governance-first pipeline generation
- Production-grade modular design

---

## 📈 Roadmap

- Scala generator support
- SQL-native pipeline generation
- UI-based visual plan inspector
- Plugin marketplace
- Observability dashboard
- Multi-workspace orchestration

---

## 🧑‍💻 Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload

### 🔥 Why this works better:
- No broken box drawing
- No alignment issues
- Renders perfectly on GitHub
- Clean and professional

## 📄 License
MIT License

Copyright (c) 2026 M R V