# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies
# gcc, make: For compiling the autograding C core
# libpq-dev: For PostgreSQL adapter (psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy python dependencies first to leverage Docker cache
COPY web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Build the C shared library for grading
# Only build the shared library, skip the executable since it relies on Windows C headers
RUN make build/libgrading.so

# Set environment variables
ENV PYTHONPATH=/app:/app/web
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application using Gunicorn with Eventlet for SocketIO support
# Wait for DB first, then start app
# -w 4: Use 4 workers to handle higher concurrency (Web IO)
CMD ["sh", "-c", "python web/wait_for_db.py && gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:8080 web.app:app"]
