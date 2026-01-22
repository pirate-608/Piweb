#!/bin/sh
# Night Watch's Window 容器启动前环境变量强校验
set -e
REQUIRED_VARS="DATABASE_URL DASHSCOPE_API_KEY SECRET_KEY FLASK_ENV REDIS_HOST REDIS_PORT SESSION_TYPE"
for var in $REQUIRED_VARS; do
  eval val=\${$var}
  if [ -z "$val" ]; then
    echo "[ERROR] 关键环境变量 $var 未定义，容器启动中止。"
    exit 11
  fi
done
exec "$@"
