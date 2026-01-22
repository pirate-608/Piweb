#!/bin/bash
# Night Watch's Window 安全停库脚本
# 支持开发/生产环境，二次确认，防误操作

set -e
source "$(dirname "$0")/_common.sh"

env=${1:-dev}  # 默认dev，可传prod
ENV_BASE=".env.${env}"
ENV_KEY=".env.key"
ENV_OUT=".env"

# 合并并导出环境变量
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
    echo "[ERROR] 关键环境变量 $var 缺失于 $ENV_OUT，停库中止。"
    exit 3
  fi
done

# 二次确认
read -p $'\033[1;31m警告：即将停止数据库服务，可能导致业务中断！\n请确认无活跃写入任务，且已备份数据。\n输入 YES 继续，其他任意键取消：\033[0m' confirm
if [[ "$confirm" != "YES" ]]; then
  echo "[CANCEL] 操作已取消，数据库未停止。"
  exit 0
fi

# 停止数据库服务（假设服务名为 db，可根据实际 docker-compose.yml 修改）
echo "[INFO] 停止数据库服务..."
docker-compose stop db
# 可选彻底关闭并移除容器：
# docker-compose down -v --remove-orphans

echo "[SUCCESS] 数据库服务已安全停止，环境：$env"
