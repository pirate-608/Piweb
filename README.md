# Auto Grading System (自动阅卷系统)

这是一个基于 C 语言核心逻辑和 Python Flask Web 界面的自动阅卷系统。支持命令行 (CLI) 和 Web 两种交互方式。

## 项目特性

*   **双模式交互**：
    *   **CLI 模式**：经典的命令行交互，支持 Windows/Linux。
    *   **Web 模式**：现代化的 Web 界面，提供更友好的用户体验。
*   **混合编程**：
    *   核心阅卷逻辑 (`grading.c`) 由 C 语言编写，编译为动态链接库 (`.dll`/`.so`)。
    *   Web 层由 Python Flask 实现，通过 `ctypes` 调用 C 语言核心库，确保高性能与逻辑复用。
*   **数据持久化**：题目和配置存储在文本文件中，方便查看和编辑。

## 目录结构

```text
auto-grading-system/
├── build/                # 编译产物 (可执行文件和动态库)
├── include/              # C 头文件
├── src/                  # C 源文件
├── web/                  # Python Web 源代码
│   ├── templates/        # HTML 模板
│   └── app.py            # Flask 主程序
├── Makefile              # 构建脚本
├── questions.txt         # 题库文件
└── README.md             # 项目说明
```

## 快速开始

### 1. 环境准备

*   **C 编译器**: GCC (MinGW for Windows)
*   **构建工具**: Make
*   **Python**: 3.8+

### 2. 编译项目

在项目根目录下运行：

```bash
make
```

这将生成：
*   `build/auto_grader.exe`: 命令行版主程序。
*   `build/libgrading.dll`: 供 Python 调用的核心动态库。

### 3. 运行命令行版 (CLI)

```bash
./build/auto_grader.exe
```
*注意：Windows 下已优化中文显示，无需担心乱码。*

### 4. 运行 Web 版

#### 安装依赖

建议使用虚拟环境：

```bash
# 创建虚拟环境 (如果尚未创建)
python -m venv .venv

# 激活虚拟环境 (Windows)
.\.venv\Scripts\Activate

# 安装依赖
pip install -r web/requirements.txt
```

#### 启动服务

```bash
python web/app.py
```

访问浏览器：[http://127.0.0.1:5000](http://127.0.0.1:5000)

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

*   **添加题目**: 可以在 Web 界面添加，也可以直接编辑 `questions.txt` (格式: `题目|答案|分值`)。
*   **修改核心逻辑**: 修改 `src/grading.c` 后，必须重新运行 `make` 更新动态库。
