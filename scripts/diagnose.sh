#!/bin/bash
# Night Watch's Window 一键诊断脚本
# 检查各容器状态、环境变量注入、数据库连接、会话密钥等

set -e

# 检查 docker-compose 版本
if command -v docker-compose >/dev/null 2>&1; then
  echo "[诊断] docker-compose 版本："
  docker-compose version
else
  echo "[ERROR] 未检测到 docker-compose，请检查环境。"
fi

echo
# 检查常用端口占用
PORTS=(8080 5432 6379 80 443)
echo "[诊断] 常用端口占用情况："
for port in "${PORTS[@]}"; do
  if netstat -ano | grep -q ":$port "; then
    echo "[WARN] 端口 $port 已被占用："
    netstat -ano | grep ":$port "
  else
    echo "[OK] 端口 $port 未被占用"
  fi
done

echo
# 自动备份 .env
if [ -f .env ]; then
  cp .env ".env.bak.$(date +%Y%m%d%H%M%S)"
  echo "[INFO] .env 已自动备份"
else
  echo "[WARN] .env 文件不存在，跳过备份"
fi

echo
# 检查 docker-compose 服务状态
echo "[诊断] docker-compose 服务状态："
docker-compose ps

echo
# 检查 web/worker/redis/db 容器环境变量
for svc in web worker redis db; do
  echo "[诊断] $svc 容器环境变量："
  docker-compose exec $svc env 2>/dev/null | grep -E 'DATABASE_URL|DASHSCOPE_API_KEY|SECRET_KEY|FLASK_ENV|REDIS_HOST|REDIS_PORT|SESSION_TYPE' || echo "[WARN] $svc 环境变量未注入或容器未运行"
  echo
  sleep 1
done

# 检查数据库连接
PGUSER=${POSTGRES_USER:-postgres}
PGPASS=${POSTGRES_PASSWORD:-postgres}
PGDB=${POSTGRES_DB:-postgres}
PGHOST=localhost
PGPORT=5432

echo "[诊断] 数据库连接测试："
if command -v psql >/dev/null 2>&1; then
  PGPASSWORD=$PGPASS psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDB -c '\l' || echo "[ERROR] 无法连接数据库 $PGDB"
else
  echo "[WARN] 未检测到 psql，跳过本地数据库连接测试。"
fi

echo
# 检查当前 .env 关键变量
if [ -f .env ]; then
  echo "[诊断] .env 关键变量："
  grep -E 'DATABASE_URL|DASHSCOPE_API_KEY|SECRET_KEY|FLASK_ENV|REDIS_HOST|REDIS_PORT|SESSION_TYPE' .env || echo "[WARN] .env 关键变量缺失"
else
  echo "[ERROR] .env 文件不存在"
fi

echo
# 检查 Flask-Session 会话密钥
if [ -f .env ]; then
  sk=$(grep SECRET_KEY .env | cut -d= -f2-)
  if [ -z "$sk" ]; then
    echo "[ERROR] .env 缺少 SECRET_KEY"
  else
    echo "[诊断] SECRET_KEY: $sk"
  fi
fi

echo
# 检查 web/worker 健康检查（HTTP 200）
for svc in web worker; do
  port=8080
  [ "$svc" = "worker" ] && port=5555
  if command -v curl >/dev/null 2>&1; then
    echo "[诊断] $svc 健康检查 (curl)："
    curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$port || echo "[WARN] $svc 未监听 $port 或未响应"
  else
    echo "[WARN] curl 未安装，跳过 $svc 健康检查"
  fi
  echo
  sleep 1
done

echo
# 检查 web/worker 日志关键报错
echo "[诊断] web/worker 容器最近关键日志："
docker-compose logs --tail=50 web worker | grep -iE 'error|fail|exception|critical' || echo "[INFO] 无关键报错"

echo
# 诊断结束
echo "[SUCCESS] 一键诊断完成。"
