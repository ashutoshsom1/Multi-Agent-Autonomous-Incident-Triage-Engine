FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock* ./

# Install dependencies into virtual environment
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install -e .

# Copy application source code
COPY . .

# Ensure virtual environment is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

EXPOSE 8000 8501

# Default command: FastAPI webhook server
CMD ["incidentops", "serve", "--host", "0.0.0.0", "--port", "8000"]
