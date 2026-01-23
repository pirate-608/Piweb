# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
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
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN rm -rf build && \
    cmake -S . -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_CXX_COMPILER=g++ \
    && cmake --build build --config Release

# Expose the port the app runs on
EXPOSE 8080

# ======（自动适配入口） ======
CMD ["sh", "/app/web/docker_entrypoint.sh"]