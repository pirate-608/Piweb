import os
import sys
import platform

class Config:
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
        RESULTS_FILE = os.path.join(BASE_DIR, 'results.json')
        
        INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
        if not os.path.exists(INSTANCE_PATH):
            os.makedirs(INSTANCE_PATH)
            
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(INSTANCE_PATH, 'data.db')
        
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
    else:
        # Development mode
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Data Paths
        DLL_PATH = os.path.join(BASE_DIR, 'build', LIB_NAME)
        DATA_FILE = os.path.join(BASE_DIR, 'questions.txt')
        RESULTS_FILE = os.path.join(BASE_DIR, 'results.json')
        
        # Database config
        WEB_DIR = os.path.dirname(os.path.abspath(__file__))
        INSTANCE_PATH = os.path.join(WEB_DIR, 'instance')
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(INSTANCE_PATH, 'data.db')
        
        # Uploads
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'web', 'static', 'uploads')

    # Security & Session Config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'auto_grading_system_dev_key_change_in_prod'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE = True # Uncomment if running over HTTPS

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

    # Exam Settings
    EXAM_DURATION_MINUTES = 60  # 考试时长（分钟）

