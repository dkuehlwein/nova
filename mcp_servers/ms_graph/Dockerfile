FROM python:3.13-slim

# Install uv and curl for health checks
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --frozen --no-cache || uv sync --no-cache

# Copy source code
COPY main.py ./
COPY src/ ./src/

# Create credentials directory
RUN mkdir -p /app/credentials

# Expose port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["uv", "run", "python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
