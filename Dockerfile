# Use an official Python runtime as a parent image
FROM python:3.11-slim



# 使用清华源加速 Debian/Ubuntu 包拉取
RUN sed -i 's@http://deb.debian.org@https://mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y \
    gcc \
    g++ \
    ninja-build \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*



# 全局COPY grader、text_analyzer、根CMakeLists.txt
WORKDIR /app
COPY grader ./grader
COPY text_analyzer ./text_analyzer
COPY CMakeLists.txt ./
COPY text_analyzer/dict ./text_analyzer/dict


# 安装Python依赖
COPY web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN rm -rf build && \
    cmake -S . -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_CXX_COMPILER=g++ \
    && cmake --build build --config Release

# Set environment variables
ENV PYTHONPATH=/app:/app/web
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8080

# ====== 生产模式（高并发Web） ======
CMD ["sh", "-c", "python web/wait_for_db.py && gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:8080 web.app:app"]
