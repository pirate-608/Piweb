#!/bin/bash
# Night Watch's Window 公共Shell函数库
# 用于环境检测、变量合并等通用逻辑

# 检查环境变量文件是否存在
echo_check_env_file() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "[ERROR] $file 不存在，请检查环境配置。"
    exit 1
  fi
}

# 合并主环境和密钥环境变量文件（已废弃，直接在主脚本合并为 .env）
echo_merge_env_files() {
  echo "[DEPRECATED] echo_merge_env_files 已废弃，主脚本已直接合并为 .env。"
}

# 导出所有变量到当前shell
echo_export_env() {
  local file="$1"
  set -a
  . "$file"
  set +a
}


# 检查 docker-compose.yml 是否存在
echo_check_compose_file() {
  if [ ! -f docker-compose.yml ]; then
    echo "[ERROR] docker-compose.yml 未找到，请在项目根目录执行。"
    exit 2
  fi
}

# 校验一组关键环境变量是否全部存在（适用于容器 entrypoint/command）
check_required_env_vars() {
  local missing=0
  for var in "$@"; do
    if [ -z "${!var}" ]; then
      echo "[ERROR] 关键环境变量 $var 未定义，启动中止。"
      missing=1
    fi
  done
  if [ $missing -ne 0 ]; then
    exit 10
  fi
}
