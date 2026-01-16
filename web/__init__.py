import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, redirect, url_for, flash, request, render_template
from web.extensions import db, login_manager, csrf, socketio, cache_redis
from config import Config
import celery_utils
import logging
from web.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Import blueprints


def create_app(config_class=Config):
    # 延迟导入所有 blueprint，避免循环依赖和多次实例化
    from web.blueprints.auth import auth_bp
    from web.blueprints.main import main_bp
    from web.blueprints.exam import exam_bp
    from web.blueprints.admin import admin_bp
    from web.blueprints.forum import forum_bp
    # 延迟导入，彻底消除循环依赖
    from web.utils.data_manager import DataManager
    from services.grading import GradingService
    data_manager = DataManager(config_class)
    grading_service = GradingService(config_class.DLL_PATH)
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
            if not os.path.exists(base_dir):
                base_dir = os.path.dirname(sys.executable)
        template_folder = os.path.join(base_dir, 'templates')
        static_folder = os.path.join(base_dir, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__)

    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    from web.extensions import migrate
    migrate.init_app(app, db)
    from flask_session import Session
    Session(app)
    
    socketio.init_app(
        app,
        message_queue=app.config.get('CELERY_BROKER_URL'),
        async_mode='eventlet',
        cors_allowed_origins='*',
        ping_timeout=30,
        ping_interval=10,
        logger=True,
        engineio_logger=True,
        max_http_buffer_size=10 * 1024 * 1024,  # 10MB
        allow_upgrades=True,
        cors_allowed_headers='*'
    )
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Updated to blueprint endpoint

    # Initialize Data Manager DB
    if not os.environ.get('SKIP_INIT_DB'):
        with app.app_context():
            # 自动建表，防止新环境下表缺失
            db.create_all()
            data_manager.init_db(app)

    # Initialize Grading Queue
    # GradingQueue needs 'lib' which is grading_service
    # It also needs 'app' for app_context
    lib = grading_service if grading_service.is_available() else None
    
    # We must delay import or use factory for GradingQueue?
    # GradingQueue stores app.
    from utils.queue_manager import GradingQueue
    num_workers = getattr(Config, 'GRADING_WORKERS', 4)
    grading_queue = GradingQueue(app, data_manager, lib, num_workers=num_workers)
    
    # Attach queue and data_manager to app so blueprints can access it
    app.grading_queue = grading_queue
    app.data_manager = data_manager

    # Initialize Celery
    app.extensions['celery'] = celery_utils.make_celery(app)

    # --- Flask-Admin 集成 ---
    from web.admin_view import init_admin
    init_admin(app)

    # --- Flask-Uploads & Flask-Dropzone 集成 ---
    from web.uploads_config import init_uploads
    app.dropzone = init_uploads(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)

    app.register_blueprint(forum_bp) # url_prefix='/forum' defined in blueprint

    # Register Global Hooks
    @app.after_request
    def add_header(response):
        # 安全响应头
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # 用 CSP frame-ancestors 替代 X-Frame-Options
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        # response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # 已弃用
        # response.headers['X-XSS-Protection'] = '1; mode=block'  # 已弃用
        response.headers['ngrok-skip-browser-warning'] = 'true'
        # 全局 Cache-Control
        if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
            # 静态资源长缓存
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        # 移除 Pragma/Expires，统一用 Cache-Control
        response.headers.pop('Pragma', None)
        response.headers.pop('Expires', None)
        # Content-Type charset=utf-8 检查
        ct = response.headers.get('Content-Type')
        if ct and 'charset' not in ct.lower():
            if ct.startswith('text/') or ct.startswith('application/json'):
                response.headers['Content-Type'] = ct + '; charset=utf-8'
        return response

    @app.before_request
    def check_exam_mode():
        from flask import session
        if session.get('in_exam'):
            # Allow: exam, static, uploads, queue status, waiting
            # Note: blueprints add prefixes. 'exam.exam'
            # Allowed endpoints:
            allowed = ['exam.exam', 'static', 'main.uploaded_file', 'exam.waiting', 'exam.queue_status']
            if request.endpoint in allowed or (request.endpoint and request.endpoint.startswith('static')):
                return
            flash('考试进行中，无法访问其他页面！', 'warning')
            return redirect(url_for('exam.exam'))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500
        
    # SocketIO Events need to be registered too.
    # They are global.
    @socketio.on('join')
    def on_join(data):
        from flask_socketio import join_room
        room = data.get('room')
        print(f"[DEBUG] join room: {room}")
        if room:
            join_room(room)

    return app
