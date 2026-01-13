# Use an official Python runtime as a parent image
FROM python:3.11-slim


# Install system dependencies
# gcc, ninja-build: For compiling the autograding C core with CMake
# libpq-dev: For PostgreSQL adapter (psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ninja-build \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


# 拷贝C端分词产物到/app/text_analyzer
WORKDIR /app/text_analyzer

# 拷贝CMake构建产物和词典
COPY build/text_analyzer/analyzer_cli.exe ./
COPY build/text_analyzer/libanalyzer.dll ./
COPY build/text_analyzer/dict ./dict

# Copy python dependencies first to leverage Docker cache
COPY web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

RUN cmake -S . -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_CXX_COMPILER=g++ \
    && cmake --build build --config Release

# Set environment variables
ENV PYTHONPATH=/app:/app/web
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8080


# ====== CLI模式（分词/测试） ======
# 如需运行CLI测试，取消下行注释
# CMD ["./analyzer_cli.exe"]

# ====== 生产模式（高并发Web） ======
CMD ["sh", "-c", "python web/wait_for_db.py && gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:8080 web.app:app"]
