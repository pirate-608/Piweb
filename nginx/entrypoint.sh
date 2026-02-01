#!/bin/sh
# 渲染 nginx 配置中的环境变量并启动 nginx
set -e
envsubst '${DOMAIN} ${SSL_CERT} ${SSL_KEY}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
echo "======= 渲染后的 default.conf 内容如下 ======="
cat /etc/nginx/conf.d/default.conf
echo "==========================================="
exec nginx -g 'daemon off;'