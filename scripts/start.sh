#!/bin/bash
# Night Watch's Window 统一环境变量管理与一键启动脚本
# 支持开发/生产环境自动合并密钥，兼容所有 docker-compose 版本

set -e
source "$(dirname "$0")/_common.sh"

env=${1:-dev}  # 默认dev，可传prod
ENV_BASE=".env.${env}"
ENV_KEY=".env.key"
ENV_OUT=".env"


# 合并环境变量为 .env
echo_check_env_file "$ENV_BASE"
if [ -f "$ENV_KEY" ]; then
  cat "$ENV_BASE" "$ENV_KEY" > "$ENV_OUT"
else
  cp "$ENV_BASE" "$ENV_OUT"
fi
echo_export_env "$ENV_OUT"
echo_check_compose_file

# 校验关键环境变量
REQUIRED_VARS=(DATABASE_URL DASHSCOPE_API_KEY SECRET_KEY FLASK_ENV REDIS_HOST REDIS_PORT SESSION_TYPE)
for var in "${REQUIRED_VARS[@]}"; do
  if ! grep -q "^$var=" "$ENV_OUT"; then
    echo "[ERROR] 关键环境变量 $var 缺失于 $ENV_OUT，启动中止。"
    exit 3
  fi
done

# 检查是否已有服务在运行，避免重复启动
if docker-compose ps | grep -q 'Up'; then
  echo "[WARN] 已有服务在运行，无需重复启动。"
  docker-compose ps
  exit 0
fi

# 根据环境选择是否 build
echo "[INFO] 启动 docker-compose..."
if [ "$env" = "prod" ]; then
  docker-compose up -d
else
  docker-compose up -d --build
fi

echo "[SUCCESS] 服务已启动，环境：$env"