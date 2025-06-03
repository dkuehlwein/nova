FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY . .

# Install dependencies
RUN uv venv
RUN uv pip install -e .

# Expose port
EXPOSE 8001

# Run the server
CMD ["uv", "run", "python", "main.py"] 