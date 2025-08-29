# InnerBoard-local Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd --create-home --shell /bin/bash innerboard

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY prompts/ ./prompts/
COPY setup.py .
COPY README.md .

# Install the application
RUN pip install -e .

# Create directories for data
RUN mkdir -p /app/data && \
    chown -R innerboard:innerboard /app

# Switch to non-root user
USER innerboard

# Set default Ollama host for container networking
ENV OLLAMA_HOST=http://host.docker.internal:11434

# Create volume for persistent data
VOLUME ["/app/data"]

# Set working directory for data
WORKDIR /app/data

# Default command
CMD ["innerboard", "--help"]
