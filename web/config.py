import os
import sys
import platform
import redis

class Config:
    # Flask-Mail 邮件配置（需根据实际邮箱服务调整）
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_SSL = True
    MAIL_USE_TLS = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your_email@qq.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your_email_password_or_smtp_token')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
    # Text Analyzer 动态库配置
    LIBANALYZER_NAME = 'libanalyzer.dll' if platform.system() == 'Windows' else 'libanalyzer.so'
    LIBANALYZER_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'build', 'text_analyzer', LIBANALYZER_NAME
    )
    # Grading Configuration
    # Auto-detect reasonable worker count: CPU count * 2, max 16, min 4
    try:
        GRADING_WORKERS = min(max(os.cpu_count() * 2, 4), 16)
    except Exception:
        GRADING_WORKERS = 4

    # Determine library extension based on OS
    system_name = platform.system()
    if system_name == 'Windows':
        LIB_NAME = 'libgrading.dll'
    elif system_name == 'Darwin':
        LIB_NAME = 'libgrading.dylib'
    else:
        LIB_NAME = 'libgrading.so'

    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        # sys.executable points to the .exe file
        BASE_DIR = os.path.dirname(sys.executable)

        # Locate DLL
        # PyInstaller 6+ onedir puts things in _internal
        internal_dir = os.path.join(BASE_DIR, '_internal')

        if hasattr(sys, '_MEIPASS'):
            # Onefile mode
            DLL_PATH = os.path.join(sys._MEIPASS, LIB_NAME)
        elif os.path.exists(os.path.join(internal_dir, LIB_NAME)):
            # Onedir mode (PyInstaller 6+)
            DLL_PATH = os.path.join(internal_dir, LIB_NAME)
        else:
            # Fallback (Onedir older or custom)
            DLL_PATH = os.path.join(BASE_DIR, LIB_NAME)

        # Data files (writable) should be in BASE_DIR (next to exe)
        DATA_FILE = os.path.join(BASE_DIR, 'questions.txt')
        # RESULTS_FILE 已废弃，无需导出

        INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
        if not os.path.exists(INSTANCE_PATH):
            os.makedirs(INSTANCE_PATH)

        # Priority: Env Var > SQLite File
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                                  'sqlite:///' + os.path.join(INSTANCE_PATH, 'data.db')

        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

    else:
        # Development mode
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Data Paths
        DLL_PATH = os.path.join(BASE_DIR, 'build', 'grader', LIB_NAME)
        DATA_FILE = os.path.join(BASE_DIR, 'questions.txt')
        # RESULTS_FILE 已废弃，无需导出

        # Database config
        WEB_DIR = os.path.dirname(os.path.abspath(__file__))
        INSTANCE_PATH = os.path.join(WEB_DIR, 'instance')

        # Priority: Env Var > SQLite File
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                                  'sqlite:///' + os.path.join(INSTANCE_PATH, 'data.db')

        # Optimize Database Connection Pool
        # Limits connections per process to avoid "Too many connections" error
        # Web (4 workers) + Celery (22 workers) = ~26 processes * (2+1) connections < 100 max
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 2,
            'max_overflow': 1,
            'pool_recycle': 1800,
        }

        # Uploads
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'web', 'static', 'uploads')

    # Security & Session Config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'auto_grading_system_dev_key_change_in_prod'
    SESSION_COOKIE_HTTPONLY = True
    # 自动切换 cookie 配置：本地开发用 Lax/False/None，生产环境用 None/True/.67656.fun
    if os.environ.get('FLASK_ENV') == 'development' or os.environ.get('LOCAL_DEV') == '1' or 'localhost' in os.environ.get('HOST', ''):
        SESSION_COOKIE_SAMESITE = 'Lax'
        SESSION_COOKIE_SECURE = False
        SESSION_COOKIE_DOMAIN = None
    else:
        SESSION_COOKIE_SAMESITE = 'None'  # HTTPS/多域名场景建议为 None
        SESSION_COOKIE_SECURE = True      # HTTPS 场景建议为 True
        SESSION_COOKIE_DOMAIN = '.67656.fun'  # 自定义域名，前面有点
    SESSION_COOKIE_PATH = '/'

    # Trusted Origins for CSRF (Add your custom domains here)
    WTF_CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8080',
        'http://127.0.0.1:8080',
        'https://*.trycloudflare.com',
        'http://67656.fun',
        'https://67656.fun'
    ]

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'txt', 'md', 'pdf', 'docx'}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB max upload size

    # Exam Settings
    EXAM_DURATION_MINUTES = 60  # 考试时长（分钟）

    # Grading Queue Config
    # 建议范围：CPU核心数 ~ 2倍CPU核心数
    # 对于 I/O 密集型（数据库读写多），可以设大一点；对于 CPU 密集型（计算多），设为核心数即可。
    # 默认自动设置为 CPU 核心数，最小为 2
    GRADING_WORKERS = max(2, os.cpu_count() or 4)

    # Redis Config
    REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
    CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'

    # Flask-Session Config
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'redis')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'grading:session:'
    try:
        SESSION_REDIS = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    except Exception as e:
        print(f"Warning: Redis configuration failed: {e}")
        SESSION_TYPE = 'filesystem'

    # Celery Config
    CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
    CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'


