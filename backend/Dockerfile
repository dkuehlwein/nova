FROM python:3.13-slim

WORKDIR /app

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libpq-dev \
    ca-certificates \
    gnupg \
    lsb-release \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
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