FROM python:3.13-slim AS base

WORKDIR /app

# Build argument to control Playwright installation (set to "false" to skip)
ARG INSTALL_PLAYWRIGHT=true

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install uv efficiently
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy only dependency files first (better layer caching)
COPY pyproject.toml uv.lock* ./

# Install dependencies (cached unless pyproject.toml changes)
RUN uv venv && uv pip install -e .

# Copy source code (separate layer for faster rebuilds)
COPY . .

# Install Playwright browser dependencies and Chromium (optional)
# Required for LAM automation (browser-based LDAP account creation)
# Skip with: docker build --build-arg INSTALL_PLAYWRIGHT=false
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && uv run playwright install chromium; \
    fi

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "python", "start_website.py"] 