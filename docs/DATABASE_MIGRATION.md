# 数据库迁移指南 (Database Migration Guide)

随着用户量的增加，默认的 SQLite 数据库可能会成为性能瓶颈（尤其是在并发写入时）。本指南将指导您将数据从 SQLite 迁移到 **PostgreSQL** (推荐) 或 MySQL。

## 1. 为什么迁移？

*   **高并发支持**：SQLite 在写入时会锁定整个数据库文件，而 PostgreSQL 支持行级锁，能支持更多人同时考试。
*   **数据完整性**：更严格的数据类型约束和事务处理。
*   **运维便利**：支持远程连接、备份和监控。

## 2. 准备工作

### A. 安装数据库服务 (以 PostgreSQL 为例)

1.  **方法一：Docker (推荐)**
    ```bash
    docker run --name pg-grading -e POSTGRES_PASSWORD=mysecretpassword -e POSTGRES_DB=grading_db -p 5432:5432 -d postgres:15
    ```

2.  **方法二：本地安装**
    *   Windows: 下载 [PostgreSQL Installer](https://www.postgresql.org/download/windows/) 安装。
    *   Linux: `sudo apt install postgresql postgresql-contrib`

### B. 安装 Python 驱动

进入虚拟环境，安装对应的驱动库：

```powershell
# 如果使用 PostgreSQL (推荐)
pip install psycopg2-binary

# 如果使用 MySQL
pip install pymysql cryptography
```

## 3. 配置文件修改

打开 `web/config.py`，找到 SQLALCHEMY 相关配置和 DLL 路径。

**修改前 (默认)**:
```python
basedir = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'data.db')
DLL_PATH = os.path.join(basedir, 'build', LIB_NAME)
```

**修改后 (示例)**:
建议优先读取环境变量，方便切换。

```python
import os

# ... 其他代码 ...

# 优先读取环境变量，如果没有则回退到 SQLite (方便开发)
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', 'mysecretpassword')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'grading_db')

if os.environ.get('USE_SQL_DB'):
    # ...
DLL_PATH = os.path.join(basedir, 'grader', 'build', LIB_NAME)
```
    # PostgreSQL
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}'
else:
    # SQLite
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'data.db')
```

## 4. 执行数据迁移

我们为您准备了一个专门的脚本 `scripts/migrate_to_sql.py`，用于将现有的 SQLite 数据完整复制到新数据库中。

**步骤：**

1.  **确保新数据库是空的**：不要手动创建表，脚本会自动创建。
2.  **确保旧数据库文件存在**：即 `web/instance/data.db`。
3.  **运行迁移脚本**：

在项目根目录下，运行：

```powershell
# 1. 激活环境
.\.venv\Scripts\Activate

# 2. 设置临时的环境变量 (告诉脚本目标数据库在哪)
$env:NEW_DB_URI = "postgresql://postgres:mysecretpassword@localhost:5432/grading_db"

# 3. 运行迁移
python scripts/migrate_to_sql.py
```

**脚本会执行以下操作：**
1. 读取 SQLite 中的 User, Question, ExamResult 等所有数据。
2. 连接到新数据库。
3. 自动在新数据库中创建表结构 (`db.create_all()`)。
4. 将数据批量导入。
5. 打印迁移结果。

## 5. 验证与上线

1.  修改 `scripts/deploy_public.ps1` 或系统环境变量，添加 `USE_SQL_DB=true` 等验证信息。
2.  启动服务。
3.  登录 Web 界面，检查用户数据和题目是否依然存在。
