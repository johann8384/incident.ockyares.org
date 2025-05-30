# Use specific version and digest for reproducibility
#FROM python:3.11.7-slim@sha256:f11725a1e96c09b1ac0dd8e8310a4f9bc7bb8c5ba3d72cfef5e17ba6e8b593c6
FROM python:3.11.7-slim

# Set labels for better metadata
LABEL maintainer="Emergency Response Team <emergency@ockyeoc.org>"
LABEL version="1.0"
LABEL description="Emergency Incident Management System"
LABEL org.opencontainers.image.source="https://github.com/your-org/emergency-incident-app"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user first
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set work directory
WORKDIR /app

# Install system dependencies with specific versions and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client=15+* \
        gdal-bin=3.6.2+* \
        libgdal-dev=3.6.2+* \
        gcc=4:12.2.0-* \
        g++=4:12.2.0-* \
        libpq-dev=15.* \
        curl=7.88.1-* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==23.3.1 && \
    pip install --no-cache-dir -r requirements.txt && \
    pip check

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories with proper permissions
RUN mkdir -p /app/static/qr_codes /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 750 /app/logs

# Remove development/build dependencies
RUN apt-get update && \
    apt-get remove -y gcc g++ && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Use gunicorn with security settings
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "app:app"]
