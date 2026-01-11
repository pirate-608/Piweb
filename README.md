
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
├── Makefile              # 构建脚本
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

### 打包发布注意事项

1. 打包前请备份 `instance/` 数据库和 `uploads/` 文件夹。
2. Windows/Linux/macOS 打包命令见下文，注意 `--add-data` 路径分隔符（Win用`;`，Linux/macOS用`:`）。
3. 打包后首次运行请检查依赖库、动态库（如 grading.dll/so/dylib）是否被正确包含。
4. 如需迁移数据，先运行一次程序生成目录，再覆盖数据文件。

---

### Docker 一键部署（推荐）

1.  **启动服务**：
    在项目根目录下打开终端，运行：
    ```powershell
    docker-compose up -d --build
    ```
2.  **访问平台**：
    浏览器打开 http://localhost:8000

### 本地开发环境（可选）

1. 安装 Python 3.11、Node.js、PostgreSQL、Redis
2. 创建虚拟环境并安装依赖：
    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
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
    系统会自动通过 Docker Compose 拉起以下服务：
    *   **web**: Python Flask 应用（Gunicorn + Eventlet，支持SocketIO，生产环境推荐）
    *   **db**: PostgreSQL 15 数据库
    *   **redis**: Redis 7.0 (缓存与消息队列)
    *   **worker**: Celery Worker (后台异步阅卷进程)
    *   **tunnel**: Cloudflare Tunnel (内网穿透 HTTP2协议)

1.  **访问应用**:
    *   **内网**: [http://localhost:8080](http://localhost:8080)
    *   **外网**: 访问您在 Cloudflare Dashboard 配置的域名 (需配置 `tunnel_token.txt`)。
    *   默认管理员账号（用户名/密码）: `admin` / `admin123`

**🌐 如何配置 Cloudflare Tunnel (外网访问)**

为了获得稳定的公网访问地址，并配合 Docker 部署使用，请按照以下步骤操作。

**⚠️ 重要提示**：Docker 容器内的隧道服务默认已配置 `--protocol http2` 参数，可自动绕过 UDP/QUIC 屏蔽。

1.  **准备 Token**:
    *   登录 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)。
    *   转到 **Networks > Tunnels**，点击 **Create a tunnel**。
    *   选择 **Cloudflared** 连接器类型。
    *   在 "Install and run a connector" 页面，**复制 `--token` 后面的那串长字符**。
    *   配置 **Public Hostname** (Service: `HTTP` : `web:8080`)。*注意：在 Docker 内部，Web 服务的主机名是 `web` 而不是 `localhost`。*

2.  **创建配置文件**:
    *   在项目根目录下创建一个名为 **`tunnel_token.txt`** 的文件。
    *   将 token **粘贴**进去 (文件中只保留这一行 token 字符串)。

3.  **启动隧道**:
    *   无需任何额外操作。只要 `tunnel_token.txt` 存在，再次运行 `docker-compose up -d --build`，隧道容器就会自动启动。
    *   您可以通过 `docker logs auto-grading-system-tunnel-1` 查看隧道连接状态。
    *   使用 `docker logs auto-grading-system-tunnel-1` 查看连接日志。

## 用户指南 (Web 版)

### 🎓 学生用户
1.  **注册/登录**：访问首页，点击右上角“注册”创建账号。
2.  **开始考试**：
    *   点击导航栏的“开始考试”。
    *   系统会随机抽取题目。
    *   答题过程中请勿刷新页面，否则进度可能丢失。
3.  **查看成绩**：
    *   提交试卷后，系统会立即判分并显示详细报告。
    *   报告中包含：总分、用时、每道题的得分与标准答案对比。
4.  **仪表盘**：
    *   首页仪表盘展示您的历史成绩趋势图。
    *   “错题分析”模块会列出您最常出错的题目，助您查漏补缺。

### 👑 管理员用户
1.  **获取权限**：
    *   目前需手动修改数据库。请使用 **PostgreSQL 客户端**（如 DBeaver、DataGrip、psql 命令行等）连接数据库。
    *   连接信息：
        - 主机：db（容器内）或 localhost（本地）
        - 端口：5432
        - 数据库名：grading_system
        - 用户名/密码：postgres/postgres
    *   找到 `user` 表，将目标用户的 `is_admin` 字段设置为 `1` (True)。
2.  **题库管理**：
    *   登录后，导航栏会出现“题库管理”入口。
    *   **添加题目**：支持输入题目内容、标准答案、分值，并可上传图片。
    *   **编辑/删除**：可对现有题目进行修改或删除。
3.  **数据同步**：
    *   **自动同步**：每当您在 Web 端添加、修改或删除题目时，系统会自动将最新数据导出到 `questions.txt`。
    *   这意味着 CLI (命令行) 版的阅卷程序也能实时获取最新的题库数据。

## 💻 运维与高级操作手册

本章节介绍了如何手动管理项目服务，适合开发者或运维人员查阅。所有命令均建议在 VS Code 的 **PowerShell** 终端中执行。

### 1. 一键维护命令

| 操作目标 | 命令 | 说明 |
| :--- | :--- | :--- |
| **Docker 启动/更新** | `docker-compose up -d --build` | **推荐**。自动构建并运行所有服务。 |
| **Docker 重启应用** | `docker-compose restart web` | 仅重启 Web 容器 (常用于数据库迁移后)。 |
| **Docker 停止** | `docker-compose down` | 停止并移除所有容器。 |
| **启动隧道** | `.\cloudflared.exe ...` | 见上文说明。 |
| **(Legacy) 脚本启动** | `.\scripts\deploy_public.ps1` | 旧版一键脚本。 |

#### **重要提示** 
当您对代码进行修改和维护时，建议先停止docker（自动断开网络连接），完成修改后再重新构建并运行：

1. 先彻底移除所有容器（可选，这会自动断开所有网络连接）
`docker-compose down`

1. 重新构建并启动（-d 后台运行，--build 确保应用了新的代码修改）
`docker-compose up -d --build`


### 2. 手动分步启动 (Legacy / 非 Docker 环境)

如果您不想使用 Docker 也不想使用脚本，可以手动分步启动各项组件（仅适用于本地开发）：

**步骤 A: 启动 Web 服务器（开发/测试可用，生产环境请用 Docker）**
```powershell
# 1. 激活虚拟环境
.\.venv\Scripts\Activate

# 2. 设置 PYTHONPATH (防止 ModuleNotFoundError)
$env:PYTHONPATH = "web"

# 3. 启动开发服务器（仅本地测试）
python web/app.py

# 4. 启动生产服务器（推荐 Gunicorn，需手动安装 eventlet）
gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:8080 web.app:app
```

**步骤 B: 启动 Cloudflare Tunnel**
保持 Web 服务器运行，新建一个终端窗口运行隧道：

*   **方式 1 (Token 模式 - 推荐)**:
    ```powershell
    # 需确保根目录下有 verify_token.txt
    .\cloudflared.exe tunnel run --token (Get-Content tunnel_token.txt)
    ```
*   **方式 2 (Name 模式 - 需本地登录)**:
    ```powershell
    # 需确保本地已配置名为 "Fishing-rod" 的隧道
    .\cloudflared.exe tunnel run Fishing-rod
    ```

### 3. 性能调优说明

为了在个人电脑或服务器上获得最佳并发性能，项目已进行以下配置：
*   **动态并发**: Docker 部署下 Gunicorn 自动支持多进程/多线程，`web/wsgi.py` 也可根据 CPU 自动调整线程数（仅本地模式）。
*   **内存保护**: `web/utils/queue_manager.py` 内置自动清理机制，定期移除陈旧的任务记录，防止内存溢出。
*   **高性能 DB**: 生产环境**仅支持 PostgreSQL**，配合连接池 (SQLAlchemy Pool) 可支持数百人同时在线考试，无需担心 `database is locked` 错误。

## 🔄 数据库迁移指南 (Upgrade)

如果您是从 v2.0 (SQLite) 升级上来的用户，请按照以下步骤迁移数据（**升级后仅支持 PostgreSQL，SQLite 仅用于历史兼容**）：

1.  **启动 Postgres 容器** (参考"前置准备")。
2.  **运行迁移脚本**：
    ```powershell
    .\.venv\Scripts\Activate
    python scripts/migrate_to_postgres.py
    ```
3.  **按提示操作**：
    *   脚本会自动检测本地的 `data.db` (SQLite)。
    *   回车确认 Postgres 连接地址 (默认: `postgresql://postgres:postgres@localhost:5432/grading_system`)。
    *   脚本会自动创建新表并将用户、题目、成绩等数据导入 Postgres。

## 常见问题

**Q: 为什么修改了题目，CLI 版没有变化？**
A: 请确保您是在 Web 管理界面进行的修改。系统会自动触发同步机制。如果您是直接修改数据库文件，则不会触发同步。

**Q: 生产环境启动报错 "ModuleNotFoundError: No module named 'config'"？**
A: 请确保使用 `deploy_public.bat` 启动，或者直接运行 `python wsgi.py`。不要直接运行 `python web/app.py` (这是开发模式)。

**Q: 如何支持更多人同时考试？**
A: 当前配置适合班级内部使用。如需支持更大规模并发（>50人），建议：
1.  确保已切换至 PostgreSQL 数据库 (默认配置)。
2.  修改 `wsgi.py` 中的 `threads` 参数，增加工作线程数。
3.  如果使用 Docker 部署，适当增加容器的 CPU/内存限额。

## 打包发布 (Windows / Linux / macOS)

本系统支持使用 PyInstaller 将 Python Web 端打包为独立的可执行文件，方便在没有 Python 环境的电脑上运行。

### 1. 准备工作

确保你已经创建了虚拟环境并安装了所有依赖（包括 `pyinstaller`）：

```bash
# 激活虚拟环境 (Windows)
.\.venv\Scripts\Activate

# 激活虚拟环境 (Linux / macOS)
source .venv/bin/activate

# 安装依赖
pip install -r web/requirements.txt
```

### ⚠️ 重要提示：数据备份

**重新打包会完全覆盖 `dist/auto_grader_web` 目录！**

如果你之前已经运行过打包后的程序，请在重新打包前**备份以下数据**，否则所有用户数据（注册信息、考试记录、上传图片）都将丢失：
1.  `dist/auto_grader_web/instance/data.db` (数据库文件)
2.  `dist/auto_grader_web/uploads/` (图片文件夹)

**建议流程**：备份上述文件 -> 运行打包命令 -> 将备份文件覆盖回原位。

### 2. 执行打包命令

在项目根目录下运行以下命令（请根据操作系统选择）：

**Windows:**

```bash
pyinstaller --name auto_grader_web --onedir --add-data "web/templates;templates" --add-data "web/static;static" --add-binary "grader/build/libgrading.dll;." --clean --noconfirm web/app.py
```

**Linux:**

```bash
pyinstaller --name auto_grader_web --onedir --add-data "web/templates:templates" --add-data "web/static:static" --add-binary "grader/build/libgrading.so:." --clean --noconfirm web/app.py
```

**macOS:**

```bash
pyinstaller --name auto_grader_web --onedir --add-data "web/templates:templates" --add-data "web/static:static" --add-binary "grader/build/libgrading.dylib:." --clean --noconfirm web/app.py
```

**参数说明**：
*   `--onedir`: 生成文件夹模式 (推荐，启动快，易于排查问题)。
*   `--add-data`: 打包 HTML 模板和静态资源 (Windows使用 `;` 分隔，Linux/macOS使用 `:` 分隔)。
*   `--add-binary`: 打包 C 语言编译生成的动态库。

### 3. 运行程序

打包完成后，生成的文件位于 `dist/auto_grader_web/` 目录下。

1.  进入 `dist/auto_grader_web/` 文件夹。
2.  (可选) 如果需要迁移旧题库，将 `questions.txt` 复制到该文件夹中。
3.  启动程序：
    *   **Windows**: 双击 `auto_grader_web.exe`。
    *   **Linux / macOS**: 在终端运行 `./auto_grader_web`。
4.  程序会自动打开浏览器访问系统。

**注意**：
*   打包后的程序数据（数据库 `instance/data.db`、上传的图片 `uploads/`）会存储在程序同级目录下，方便备份和迁移。

## 公网访问 (Ngrok)

如果你想将本地运行的 Web 服务分享给他人访问，可以使用 `ngrok`。

1.  **安装 Ngrok**: [下载并注册](https://ngrok.com/)。
2.  **启动映射**:
    确保你的 Flask 应用正在运行 (端口 5000)，然后在新的终端窗口中运行：
    ```bash
    ngrok http 5000
    ```
    *提示：ngrok 免费版首次访问可能会显示警告页，点击 "Visit Site" 继续即可。*

3.  **获取链接**:
    复制终端显示的 `Forwarding` 地址 (例如 `https://xxxx-xxxx.ngrok-free.app`) 发送给其他人即可访问你的自动阅卷系统。

## 开发说明

*   **热重载开发**：推荐用 Flask 的开发模式（见上文），可自动重启。
*   **SQLAlchemy 实例唯一性**：全项目只允许一个 db 实例，详见“高级运维说明”。
*   **ngrok/Cloudflare Tunnel**：开发可用 ngrok，生产建议用 Cloudflare Tunnel，配置见上文。
*   **打包与迁移**：打包前务必备份数据，首次运行后再覆盖数据文件。
*   **常见问题排查**：遇到数据库写入不生效、500 错误、session 异常，优先检查 SQLAlchemy 实例和导入路径。

*   **添加题目**: 可以在 Web 界面添加（支持图片|分类(可选)和多行文本），也可以直接编辑 `questions.txt`。
    *   格式: `题目|答案|分值|图片文件名(可选)`
    *   注意：直接编辑文件时，换行符请使用 `[NEWLINE]` 代替。
*   **修改核心逻辑**: 修改 `grader/src/grading.c` 后，必须重新运行 `make` 更新动态库。
*   [GitHub仓库地址](https://github.com/pirate-608/NWWeb)
