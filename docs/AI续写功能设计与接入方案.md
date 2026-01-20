# AI续写功能设计与接入方案

## 1. 目标与选型
- 实现“AI智能续写”功能，支持论坛/工坊等文本场景。
- 首选通义千问（DashScope）和 Azure OpenAI，支持后续扩展。
- 兼容 Flask 官方 SDK，支持 Flask-RESTx 优化。

## 2. 技术方案
### 2.1 后端
- 新建 `web/services/ai_writer.py`，封装 DashScope/Azure OpenAI API 调用。
- 新建 `web/blueprints/ai.py`，提供 `/api/ai/continue` RESTful 接口。
- 读取 API Key（如 `DASHSCOPE_API_KEY`）自 `.env`。
- 支持模型切换（配置项控制）。
- 启用缓存：对相同输入（prompt+参数）返回历史结果，减少重复调用。
- 输出截断：max_tokens=300，防止超长输出和高额费用。
- 错误处理：API异常友好提示，超时/限流保护。

### 2.2 前端
- 在工坊编辑器、论坛发帖等页面集成“AI续写”按钮。
- 前端调用 `/api/ai/continue`，传递上下文、参数，展示返回内容。
- 支持多轮续写、参数可调（如温度、风格等）。

### 2.3 依赖与安全
- 官方 SDK：`dashscope`、`openai`，如需 Flask-RESTx 则引入。
- API Key 仅后端可见，前端不暴露。
- 日志与监控：记录调用量、缓存命中率、异常。

## 3. 目录结构建议
- `web/services/ai_writer.py`  —— 统一模型API封装
- `web/blueprints/ai.py`      —— RESTful接口
- `web/templates/workshop/editor.html` —— 前端入口
- `web/utils/cache.py`        —— 简单缓存实现（如LRU/内存/Redis）

## 4. 关键实现要点
- 支持 prompt+参数 hash 作为缓存 key，优先用内存缓存，后续可接 Redis。
- 支持多模型切换（如 dashscope/openai），接口参数兼容。
- 输出长度、费用、异常均有保护。
- 代码风格与现有项目一致，便于维护。

## 5. 后续扩展
- 支持更多模型（如文心一言、本地大模型）。
- 支持异步任务、流式输出。
- 支持用户自定义 prompt 模板。

---
如需详细接口文档、代码样例或前端集成方案，请随时提出。
