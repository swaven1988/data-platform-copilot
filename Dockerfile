# -----------------------------
# Builder (wheels)
# -----------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /build/pyproject.toml
COPY README.md /build/README.md

RUN python -m pip install --no-cache-dir -U pip setuptools wheel

# Build wheels for all deps from pyproject
RUN python -m pip wheel --no-cache-dir --no-deps -w /wheels .

# -----------------------------
# Runtime (lean)
# -----------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install wheels (no build tools here)
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir -U pip \
 && python -m pip install --no-cache-dir /wheels/*.whl \
 && rm -rf /wheels

# App files
COPY app /app/app
COPY templates /app/templates
COPY tools /app/tools
COPY copilot_spec.yaml /app/copilot_spec.yaml
COPY packaging_manifest.json /app/packaging_manifest.json
COPY project_tree.txt /app/project_tree.txt
COPY project_file_paths.txt /app/project_file_paths.txt
COPY logging.yaml /app/logging.yaml

# ---- CREATE NON-ROOT USER FIRST ----
RUN adduser --disabled-password --gecos '' appuser

# ---- CREATE WORKSPACE AND FIX OWNERSHIP ----
RUN mkdir -p /app/workspace \
 && chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-config", "logging.yaml"]