# Auto Grading System (自动阅卷系统)

这是一个基于 C 语言核心逻辑和 Python Flask Web 界面的自动阅卷系统。支持命令行 (CLI) 和 Web 两种交互方式。

## 项目特性

*   **双模式交互**：
    *   **CLI 模式**：
        *   经典的命令行交互，支持 Windows/Linux。
        *   **全新彩色 UI**：引入 ANSI 颜色支持，界面更美观清晰。
        *   **可视化进度条**：考试过程中实时显示答题进度。
        *   **历史记录图表**：在终端内直接绘制 ASCII 柱状图，展示历史成绩趋势。
        *   **实时计时器**：考试时显示已用时间。
        *   **自动清屏**：优化交互流程，保持界面整洁。
    *   **Web 模式**：
        *   **用户系统**：
            *   **注册/登录**：完整的用户认证流程。
            *   **权限管理**：区分管理员（管理题库）和普通学生（仅能考试）。
        *   **数据仪表盘**：
            *   **成绩趋势图**：可视化展示最近 7 次考试的成绩变化。
            *   **错题分析**：自动统计并展示最高频的 5 个错题，辅助针对性复习。
        *   **现代化界面**：基于 Bootstrap 5 的响应式设计。
        *   **考试安全**：考试模式锁定、防后退、防意外刷新。
        *   **数据保护**：客户端表单自动缓存（LocalStorage）。
        *   **富文本支持**：支持题目多行输入和图片上传。
        *   **随机化出题**：每次考试题目顺序自动打乱。
*   **智能评分**：
    *   引入 **Levenshtein 编辑距离算法**，支持模糊匹配。
    *   不再要求答案完全一致，允许一定程度的错别字（如 "Hello" 与 "Hllo"），评分更加人性化。
*   **混合编程**：
    *   核心阅卷逻辑 (`grading.c`) 由 C 语言编写，编译为动态链接库 (`.dll`/`.so`)。
    *   Web 层由 Python Flask 实现，通过 `ctypes` 调用 C 语言核心库，确保高性能与逻辑复用。
*   **数据持久化**：
    *   **SQLite 数据库**：使用 `instance/data.db` 存储题目和考试记录，替代了旧版的文本文件，数据更安全、查询更高效。
    *   **自动迁移**：首次运行时会自动将旧版 `questions.txt` 和 `results.json` 的数据迁移到数据库中。

## 目录结构

```text
auto-grading-system/
├── build/                # 编译产物 (可执行文件和动态库)
├── include/              # C 头文件
├── src/                  # C 源文件
├── web/                  # Python Web 源代码
│   ├── instance/         # 数据库文件 (data.db)
│   ├── static/           # 静态资源 (uploads/, js/, css/)
│   ├── templates/        # HTML 模板
│   │   ├── auth/         # 认证相关 (login.html, register.html)
│   │   ├── ...           # 其他页面模板
│   ├── utils/            # 工具模块
│   │   └── data_manager.py # 数据管理类
│   ├── models.py         # 数据库模型
│   ├── app.py            # Flask 主程序
│   └── config.py         # 项目配置
├── Makefile              # 构建脚本
├── setup.bat             # Windows 一键安装/启动脚本
├── cli_history.txt       # CLI 模式本地历史记录
├── questions.txt         # 旧版题库文件 (仅用于迁移)
└── README.md             # 项目说明
```

## 快速开始

### 方式一：一键启动 (推荐 Windows 用户)

直接双击运行项目根目录下的 `setup.bat` 脚本。
该脚本会自动完成以下操作：
1.  检查环境 (Python/Make)。
2.  清理旧的构建文件。
3.  编译 C 语言核心库。
4.  创建 Python 虚拟环境并安装依赖。
5.  提供启动菜单 (Web 版 / CLI 版)。

### 方式二：手动配置

#### 1. 环境准备

*   **C 编译器**: GCC (MinGW for Windows)
*   **构建工具**: Make
*   **Python**: 3.8+

#### 2. 编译项目

在项目根目录下运行：

```bash
make
```

这将生成：
*   `build/auto_grader` (Windows下为 `.exe`): 命令行版主程序。
*   `build/libgrading` (Windows下为 `.dll`, Linux下为 `.so`, macOS下为 `.dylib`): 供 Python 调用的核心动态库。

#### 3. 运行命令行版 (CLI)

Windows:
```bash
./build/auto_grader.exe
```

Linux / macOS:
```bash
./build/auto_grader
```
*注意：CLI 版本已升级为彩色界面，支持中文显示。*

#### 4. 运行 Web 版

**安装依赖**

建议使用虚拟环境：

```bash
# 创建虚拟环境 (如果尚未创建)
python -m venv .venv

# 激活虚拟环境 (Windows)
.\.venv\Scripts\Activate

# 激活虚拟环境 (Linux / macOS)
source .venv/bin/activate

# 安装依赖
pip install -r web/requirements.txt
```

**启动服务**

```bash
python web/app.py
```

访问浏览器：[http://127.0.0.1:5000](http://127.0.0.1:5000)

## 用户指南 (Web 版)

1.  **注册账号**：首次访问请点击右上角“注册”创建一个新账号。
2.  **默认权限**：新注册用户默认为**学生**权限，可以进行考试、查看历史和仪表盘。
3.  **管理员权限**：
    *   管理员拥有“题库管理”功能的访问权限。
    *   **获取方法**：目前需手动修改数据库。使用 SQLite 工具打开 `web/instance/data.db`，找到 `user` 表，将目标用户的 `is_admin` 字段设置为 `1` (True)。
4.  **题库管理 (管理员)**：
    *   **添加题目**：支持上传图片，图片会自动重命名并保存。
    *   **编辑题目**：可以修改题目内容、答案、分数，也可以勾选“删除当前图片”来移除已上传的图片。
    *   **删除题目**：在管理列表中直接删除题目。

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
pyinstaller --name auto_grader_web --onedir --add-data "web/templates;templates" --add-data "web/static;static" --add-binary "build/libgrading.dll;." --clean --noconfirm web/app.py
```

**Linux:**

```bash
pyinstaller --name auto_grader_web --onedir --add-data "web/templates:templates" --add-data "web/static:static" --add-binary "build/libgrading.so:." --clean --noconfirm web/app.py
```

**macOS:**

```bash
pyinstaller --name auto_grader_web --onedir --add-data "web/templates:templates" --add-data "web/static:static" --add-binary "build/libgrading.dylib:." --clean --noconfirm web/app.py
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

*   **添加题目**: 可以在 Web 界面添加（支持图片|分类(可选)和多行文本），也可以直接编辑 `questions.txt`。
    *   格式: `题目|答案|分值|图片文件名(可选)`
    *   注意：直接编辑文件时，换行符请使用 `[NEWLINE]` 代替。
*   **修改核心逻辑**: 修改 `src/grading.c` 后，必须重新运行 `make` 更新动态库。
