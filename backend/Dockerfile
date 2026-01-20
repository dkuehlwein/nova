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

# Install Playwright browser dependencies and Chromium
# Required for LAM automation (browser-based LDAP account creation)
RUN apt-get update && apt-get install -y \
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
    && rm -rf /var/lib/apt/lists/*

# Install Playwright Chromium browser
RUN uv run playwright install chromium

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "python", "start_website.py"] 