FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /bin/

WORKDIR /app

# Install runtime dependencies into a project venv (cached until the lock changes).
COPY pyproject.toml requirements.txt uv.lock ./
RUN uv sync --frozen --no-install-project

# Run from the source checkout; PYTHONPATH makes the `app` package importable.
COPY app ./app

ENV PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
