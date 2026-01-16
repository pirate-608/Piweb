# 67656.fun 草稿保存/推送 WebSocket 问题诊断记录

## 现象
- 草稿保存请求（/workshop/editor 页面）在公网67656.fun下无推送响应，Network中WebSocket连接一直处于“待处理”状态。
- wss://67656.fun/socket.io/?EIO=4&transport=websocket 连接状态码101（Switching Protocols），但前端表现为“WebSocket挂起/无推送”。
- 本地localhost环境一切正常。

## 关键日志与链路分析

### 1. WebSocket链路
- WebSocket握手成功（101），但前端多次报“WebSocket is closed before the connection is established”。
- 日志显示部分content字段为“socket.io.min.js:6 WebSocket connection to ... failed: WebSocket is closed before the connection is established.”，为前端主动上报异常。

### 2. 后端日志
- web日志：每次保存草稿请求均能正常到达，能识别用户、解析JSON、进入save_draft逻辑。
- worker日志：Celery任务正常执行，内容分析、保存草稿均返回success，无异常报错。
- 某些请求content为二进制（如docx/pdf），Celery日志报“A string literal cannot contain NUL (0x00) characters.”，但与WebSocket链路无关。
- 绝大多数文本内容保存均成功，worker端能正常推送“草稿已保存”。
- 但WebSocket推送消息未能到达前端，前端表现为“WebSocket挂起/无推送”。

### 3. CSRF/session链路
- web日志多次显示“[CSRF DEBUG] session: None”，即Flask session未能识别，尽管请求头和cookie均已带上session。
- 这通常是代理链路（cloudflared/nginx）未正确转发cookie/session，或Flask session配置与实际域名/协议不符。

### 4. 推送链路
- worker端推送无报错，说明Redis消息队列畅通。
- web端未见socketio.emit相关日志，怀疑socketio服务端未能正确识别session或房间，导致推送丢失。

## 结论与建议
- 重点排查web服务端Flask-SocketIO的session/cookie配置，确保SESSION_COOKIE_DOMAIN、SESSION_COOKIE_SECURE、SESSION_COOKIE_SAMESITE等参数与67656.fun域名、https协议完全匹配。
- 检查cloudflared代理是否有header/cookie剥离或篡改，确保WebSocket和HTTP请求的cookie一致性。
- 检查web/__init__.py、config.py、extensions.py中关于session、socketio初始化的所有参数，确认message_queue、CORS、cookie策略无误。
- 建议采集web/extensions.py和web/__init__.py的完整内容，进一步分析Flask-SocketIO与session集成细节。

---

> 诊断时间：2026-01-15
> 采集日志：web/worker日志、cloudflared日志、Network抓包
> 主要结论：session识别异常、WebSocket推送未达前端，需重点排查session/cookie链路与Flask-SocketIO配置。
