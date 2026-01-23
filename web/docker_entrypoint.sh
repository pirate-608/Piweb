#!/bin/sh
# Night Watch's Window 容器启动前环境变量强校验
set -ex
echo "[Entrypoint] 当前执行命令: $@"
echo "[Entrypoint] 关键环境变量校验:"
REQUIRED_VARS="DATABASE_URL DASHSCOPE_API_KEY SECRET_KEY FLASK_ENV REDIS_HOST REDIS_PORT SESSION_TYPE"
for var in $REQUIRED_VARS; do
  eval val=\${$var}
  echo "$var=$val"
  if [ -z "$val" ]; then
    echo "[ERROR] 关键环境变量 $var 未定义，容器启动中止。"
    exit 11
  fi
done
echo "[Entrypoint] 开始执行主命令..."

# 判断是否为 celery worker 进程（通过命令行参数包含 celery 且包含 worker）
if echo "$@" | grep -q 'celery' && echo "$@" | grep -q 'worker'; then
  echo "[Entrypoint] 检测到 celery worker 启动命令，直接执行..."
  exec "$@"
else
  # 自动切换 gevent/gunicorn 或 flask run，仅 web 服务适用
    if [ "$USE_GEVENT" = "true" ]; then
      echo "[Entrypoint] 检测到 USE_GEVENT=true，优先使用 gunicorn --preload --worker-class gevent 启动..."
      exec python -m web.socketio_entry
    else
      echo "[Entrypoint] 未检测到 USE_GEVENT=true，使用 Flask 原生开发服务器..."
      export FLASK_APP=web/app.py
      exec flask run --host=0.0.0.0 --port=8080
    fi
fi
