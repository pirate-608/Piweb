
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from web.config import Config
from flask_session import Session
from flask_migrate import Migrate
from flask_mail import Mail

import redis
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
SOCKETIO_REDIS_URL = f"redis://{getattr(Config, 'REDIS_HOST', 'redis')}:{getattr(Config, 'REDIS_PORT', 6379)}/0"
socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins='*',
    message_queue=SOCKETIO_REDIS_URL,
    ping_timeout=30,
    ping_interval=10,
    logger=True,
    engineio_logger=True,
    max_http_buffer_size=10 * 1024 * 1024,  # 10MB
    allow_upgrades=True,
    cors_allowed_headers='*'
)

# Flask-Mail
mail = Mail()

# Redis Access
cache_redis = None
try:
    from web.config import Config
    cache_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    cache_redis.ping()
except Exception as e:
    print(f"Warning: Redis cache connection failed: {e}")
    cache_redis = None
from flask import request
# SocketIO事件日志
@socketio.on('connect')
def handle_connect():
    print(f"[SocketIO] Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[SocketIO] Client disconnected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    print(f"[SocketIO] Client {request.sid} join room: {room}")
    socketio.enter_room(request.sid, room)

@socketio.on('leave')
def handle_leave(data):
    room = data.get('room')
    print(f"[SocketIO] Client {request.sid} leave room: {room}")
    socketio.leave_room(request.sid, room)

@socketio.on('draft_status')
def handle_draft_status(data):
    print(f"[SocketIO] draft_status event received: {data}")
