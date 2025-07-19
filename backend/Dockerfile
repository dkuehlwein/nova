FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files (but exclude .venv first)
COPY pyproject.toml ./
COPY . .

# Remove any existing venv from host to prevent path issues
RUN rm -rf .venv

# Install dependencies fresh in container
RUN uv venv
RUN uv pip install -e .

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "python", "start_website.py"] 