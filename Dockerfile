# Use an official Python runtime as a parent image
FROM python:3.11-slim


# Install system dependencies
# gcc, ninja-build: For compiling the autograding C core with CMake
# libpq-dev: For PostgreSQL adapter (psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    ninja-build \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy python dependencies first to leverage Docker cache
COPY web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

RUN cmake -S . -B build -G Ninja && cmake --build build --target grader_libgrading_so

# Set environment variables
ENV PYTHONPATH=/app:/app/web
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application using Gunicorn with Eventlet for SocketIO support
# Wait for DB first, then start app
# ====== 开发模式（热重载） ======
#CMD ["sh", "-c", "python web/wait_for_db.py && FLASK_APP=web/app.py FLASK_ENV=development flask run --host=0.0.0.0 --port=8080"]

# ====== 生产模式（高并发） ======
CMD ["sh", "-c", "python web/wait_for_db.py && gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:8080 web.app:app"]
