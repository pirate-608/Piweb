from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask_session import Session
import redis
from web.config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

# Imports that depend on db/models must come AFTER db is defined to avoid circular import errors
from web.utils.data_manager import DataManager
from services.grading import GradingService

# Data Manager & Grading Service
data_manager = DataManager(Config)
grading_service = GradingService(Config.DLL_PATH)

# Redis Access
try:
    cache_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    cache_redis.ping()
except Exception as e:
    print(f"Warning: Redis cache connection failed: {e}")
    cache_redis = None
