# Stage 1: Builder
FROM python:3.14.4-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Stage 2: Production
FROM python:3.14.4-slim

# Set environment variables for Python and cache directories
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    NLTK_DATA=/home/appuser/nltk_data

WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -m -d /home/appuser appuser

# Copy the virtual environment from the builder stage with ownership
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application code with ownership
COPY --chown=appuser:appgroup . .

# Make sure no write permissions are assigned to the copied resources
RUN chmod -R a-w /app /opt/venv

# Switch to the non-root user
USER appuser

# Expose port and run the application
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
