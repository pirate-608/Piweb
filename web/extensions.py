from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask_session import Session
from flask_migrate import Migrate

import redis
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

# Redis Access
cache_redis = None
try:
    from web.config import Config
    cache_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    cache_redis.ping()
except Exception as e:
    print(f"Warning: Redis cache connection failed: {e}")
    cache_redis = None
