from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from web.config import Config
from flask_session import Session
from flask_migrate import Migrate

import redis
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
SOCKETIO_REDIS_URL = f"redis://{getattr(Config, 'REDIS_HOST', 'redis')}:{getattr(Config, 'REDIS_PORT', 6379)}/0"
socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins='*',
    message_queue=SOCKETIO_REDIS_URL
)

# Redis Access
cache_redis = None
try:
    from web.config import Config
    cache_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    cache_redis.ping()
except Exception as e:
    print(f"Warning: Redis cache connection failed: {e}")
    cache_redis = None
