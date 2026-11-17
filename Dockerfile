# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.14.9-slim-trixie@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8

# --- Stage 1: build the virtualenv with Poetry ---
FROM ${PYTHON_IMAGE} AS builder

ARG POETRY_VERSION=2.5.1
ENV PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_IN_PROJECT=1 \
  POETRY_CACHE_DIR=/tmp/poetry-cache

RUN python -m venv /opt/poetry \
  && /opt/poetry/bin/pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/tmp/poetry-cache \
  /opt/poetry/bin/poetry install --only main --no-root --no-directory

COPY README.md CHANGELOG.md ./
COPY competitor_pulse ./competitor_pulse
RUN /opt/poetry/bin/poetry build --format wheel \
  && .venv/bin/pip install --no-deps dist/*.whl \
  && .venv/bin/pip uninstall --yes pip \
  && .venv/bin/python -m compileall -q .venv/lib

# --- Stage 2: runtime ---
FROM ${PYTHON_IMAGE} AS runtime

ENV PATH=/app/.venv/bin:$PATH \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

# Unprivileged user with no home and no login shell. The system pip is removed:
# nothing installs packages at runtime.
RUN groupadd --system --gid 10001 competitor-pulse \
  && useradd --system --uid 10001 --gid competitor-pulse --no-create-home \
  --home-dir /nonexistent --shell /usr/sbin/nologin competitor-pulse \
  && python -m pip uninstall --yes pip

WORKDIR /app

# Owned by root and not writable by the app user.
COPY --from=builder /app/.venv /app/.venv
# Alembic reads its settings from pyproject.toml ([tool.alembic]) in the working directory,
# so the same image can run the migrations: `alembic upgrade head`.
COPY pyproject.toml ./
COPY migrations ./migrations

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["competitor_pulse"]
