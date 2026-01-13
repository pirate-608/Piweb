# Night Watch's Window (NWW-守夜人之窗)

守夜人之窗（NWW2026）是一个现代化的在线答题与社区平台，融合 C 语言高性能阅卷、Python Web 后端、实时数据推送与容器化部署。适用于教学、竞赛、练习等多场景。

## ⭐ 项目亮点

- **全栈容器化部署**：一键启动，环境一致，支持生产级运维。
- **C 语言高性能阅卷**：核心算法用 C 实现，Python `ctypes` 融合，速度与兼容性兼备。
- **异步任务队列**：Celery + Redis，支持高并发、实时进度推送。
- **PostgreSQL 数据库**：企业级数据一致性与扩展性。
- **WebSocket 实时推送**：考试进度、消息通知秒级同步。
- **题库自动同步**：Web 端题库变更自动导出至 CLI 题库，保障一致性。
- **现代响应式界面**：Bootstrap 5，移动端友好。

## 🏗️ 目录结构

```text
NWW2026/
├── grader/
│   ├── build/            # C 语言编译产物
│   ├── include/          # C 头文件
│   └── src/              # C 源文件
├── web/                  # Python Web 源代码（主入口）
│   ├── instance/         # 数据库文件
│   ├── static/           # 静态资源
│   ├── templates/        # HTML 模板
│   ├── utils/            # 工具模块
│   ├── models.py         # 数据库模型
│   ├── app.py            # Flask 主程序
│   └── config.py         # 配置
├── CMakeLists.txt        # CMake 构建脚本
├── scripts/              # 部署/迁移脚本
├── questions.txt         # 题库数据（Web端自动导出）
├── Dockerfile            # 容器构建
├── docker-compose.yml    # 多服务编排
└── README.md             # 项目说明
```

## 🚀 快速开始

## 🛠️ 开发环境与高级运维说明

### 开发环境下热重载模式

开发调试推荐使用 Flask 的热重载：

```powershell
cd web
set FLASK_APP=app.py
set FLASK_ENV=development
flask run
```
或直接：
```powershell
python app.py
```
此时代码变动会自动重启服务，便于调试。

**注意：** 热重载仅适用于开发环境，生产环境请用 Gunicorn + Eventlet。

### SQLAlchemy 多路径/多实例风险说明

**严禁**在项目中多次实例化 `SQLAlchemy()` 或通过不同路径（如 web/extensions.py、web/models.py、web/blueprints/*）重复导入/创建 db 实例，否则会导致：
- 数据库连接池混乱，session 绑定异常
- Flask 上下文丢失，出现 `RuntimeError: No application found` 或 `UnboundExecutionError`
- 数据写入不生效、回滚、死锁等连锁问题

**最佳实践：**
1. 只在 `web/extensions.py` 实例化一次 db，并全项目统一 `from web.extensions import db`。
2. 不要在 models.py、blueprints、tasks.py 等文件重复 new SQLAlchemy()。
3. 所有模型、数据操作均用同一个 db 实例。

如遇到数据库写入不生效、500 错误、session 相关异常，请优先排查此问题。

### Ngrok 配置与公网穿透

1. 注册并下载 ngrok（https://ngrok.com/），登录后获取 authtoken。
2. 运行：
    ```bash
    ngrok config add-authtoken <你的token>
    ngrok http 5000
    ```
3. 生产环境建议用 Cloudflare Tunnel，开发/演示可用 ngrok，注意免费版有流量/连接数限制。


### C 代码编译与构建（CMake 方式）

本项目 C 语言核心阅卷模块已切换为 CMake 构建方式，支持跨平台编译。

#### 1. 安装 CMake
请先确保已安装 [CMake](https://cmake.org/download/) 3.15 及以上版本。

#### 2. 构建流程
##### 构建（以Windows为例）：

```powershell
 cd D:\NWW2026
 Remove-Item -Recurse -Force build #清理旧的构建产物
cmake --build build --target clean #此方法不会删除整个 build 目录，只会清理中间文件。如需完全干净的环境，建议直接删除整个 build 目录再重新构建。
cmake -S . -B build
cmake --build build --config Release #构建产物会自动生成到各子模块的build目录下。
```

#### 执行测试：

```powershell
cd build/grader
.\auto_grader_cli.exe
# 或
cd build/text_analyzer
.\analyzer_cli.exe
```

---

### Web 部署

#### Docker 一键部署（推荐）

1.  **启动服务**：
    在项目根目录下打开终端，运行：
    ```powershell

    docker-compose up -d --build #启动所有服务

    docker-compose restart web #仅重新启动 web 服务

    docker-compose restart web worker #重启 web 和 celery worker 进程

    docker-compose down  #停止容器进程

    Warning！You need to be careful using following command!

    docker-compose down -v #删除所有容器和挂载的卷(慎用！会格式化所有数据！)

    ```
2.  **访问平台**：
    浏览器打开 http://localhost:8000

#### 本地开发环境（可选）

1. 安装 Python 3.11、Node.js、PostgreSQL、Redis
2. 创建虚拟环境并安装依赖：
    ```powershell
    python -m venv .venv
    .venv-1\Scripts\activate
    pip install -r web/requirements.txt
    ```
3. 启动开发服务：
    ```powershell
    cd web
    flask run
    ```

## 🧑‍💻 贡献指南

欢迎 PR、Issue、建议！

- 代码风格：PEP8（Python）、Google C Style（C）
- 分支管理：feature/xxx、bugfix/xxx
- 提交信息：简明扼要，建议英文

## 📄 许可证

MIT License，详见 LICENSE 文件。

## 📬 联系方式

- 项目主页：https://github.com/nightwatch2026/NWW2026
- 邮箱：huangmaidou608@outlook.com

---
如有任何问题或建议，欢迎通过 Issue 或邮件联系！