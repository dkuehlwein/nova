# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies
RUN uv pip install --system -e .

# Copy source code
COPY main.py ./
COPY src ./src

# Create non-root user
RUN useradd -m -u 1001 mcp-user && chown -R mcp-user:mcp-user /app
USER mcp-user

# Environment variables (override with docker run -e)
ENV LINEAR_API_KEY=""
ENV LINEAR_API_URL="https://api.linear.app/graphql"
ENV GOOGLE_API_KEY=""
ENV GOOGLE_MODEL_NAME="gemini-1.5-flash"
ENV HOST="0.0.0.0"
ENV PORT="8003"

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/tools/list || exit 1

# Run the server
CMD ["python", "main.py"] 