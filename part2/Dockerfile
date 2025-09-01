# Updated Dockerfile for Insurance RAG API with PostgreSQL and Google Gemini
# FROM python:3.11-slim

# # Set environment variables
# ENV PYTHONUNBUFFERED=1 \
#     PYTHONDONTWRITEBYTECODE=1 \
#     PIP_NO_CACHE_DIR=1

# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc \
#     g++ \
#     libpq-dev \
#     curl \
#     && rm -rf /var/lib/apt/lists/* \
#     && apt-get clean

# # Create non-root user
# RUN groupadd -r appuser && useradd -r -g appuser appuser

# # Set work directory
# WORKDIR /app

# # Copy and install Python dependencies
# COPY requirements.txt .
# RUN pip install --upgrade pip && pip install -r requirements.txt

# # Copy application code
# COPY src/ ./src/
# COPY .env.example .env

# # Set ownership
# RUN chown -R appuser:appuser /app

# # Switch to non-root user
# USER appuser

# # Expose port
# EXPOSE 8000

# # Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# # Start application
# CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]