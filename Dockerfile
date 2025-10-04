# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

# Stage 2: Application - Create the final image
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user for security
RUN addgroup --system app && adduser --system --group app

# Install system dependencies for the application and for running all services
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg supervisor redis-server curl && rm -rf /var/lib/apt/lists/*

# Copy installed Python dependencies from the builder stage
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Verify outbound connectivity to the diacritizer service
RUN curl -s --head https://arabic-tashkel-47a234e0f5bf.hosted.ghaymah.systems/diacritize

# Copy the application code
COPY . .

# Copy the supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Change ownership of the app directory to the non-root user
# This is for the celery and uvicorn processes
RUN chown -R app:app /app

# Expose the port Uvicorn will listen on. Your cloud platform will likely use this.
# The actual port is set by the PORT environment variable (defaulting to 8000).
EXPOSE 8000

# The main command to run when the container starts.
# This starts Supervisor, which in turn starts and manages redis, celery, and uvicorn.
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]