FROM python:3.11-slim

# Install uv and curl for health checks
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy source code
COPY main.py ./
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server with required arguments
CMD ["uv", "run", "python", "main.py", "--creds-file-path", "/app/credentials.json", "--token-path", "/app/token.json", "--host", "0.0.0.0", "--port", "8000"] 