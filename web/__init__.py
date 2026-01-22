import os
import sys
from pathlib import Path

from flask import Flask, redirect, url_for, flash, request, render_template
import logging

# 基础扩展，确保不直接使用它们，只导入
from web.extensions import db, login_manager, csrf, socketio, cache_redis, migrate
from web.config import Config
from web.models import User
from flask_session import Session

# 设置路径 - 放在最前面
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
        if not os.path.exists(base_dir):
            base_dir = os.path.dirname(sys.executable)
    template_folder = os.path.join(base_dir, 'templates')
    static_folder = os.path.join(base_dir, 'static')
else:
    template_folder = 'templates'
    static_folder = 'static'

# --- 关键环境变量校验（放在最前面）---
def _validate_environment():
    """验证必需的环境变量"""
    REQUIRED_ENV_VARS = [
        'DATABASE_URL', 
        'DASHSCOPE_API_KEY', 
        'SECRET_KEY', 
        'FLASK_ENV', 
        'REDIS_HOST', 
        'REDIS_PORT', 
        'SESSION_TYPE'
    ]
    
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print(f"[FATAL] 缺少关键环境变量: {', '.join(missing)}，程序终止。", file=sys.stderr)
        sys.exit(100)

# 立即执行环境验证
_validate_environment()

@login_manager.user_loader
def load_user(user_id):
    """用户加载器回调函数"""
    return User.query.get(int(user_id))

def create_app(config_class=Config):
    """
    Flask应用工厂函数
    修正要点：
    1. 单一初始化顺序：配置 -> 扩展 -> 蓝图 -> 辅助服务
    2. 避免在配置加载前初始化任何依赖配置的组件
    3. 确保所有数据库操作都在应用上下文中进行
    """
    
    # 1. 创建Flask应用实例
    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder
    )
    
    # 2. 加载配置（必须首先执行）
    app.config.from_object(config_class)
    
    # 3. 初始化所有扩展（顺序很重要）
    _initialize_extensions(app)
    
    # 4. 数据库版本检查（在应用上下文中）
    with app.app_context():
        _check_database_version(app)
    
    # 5. 初始化数据管理和评分服务（依赖配置）
    _initialize_services(app, config_class)
    
    # 6. 注册蓝图（避免循环导入）
    _register_blueprints(app)
    
    # 7. 初始化管理员界面和上传组件
    _initialize_admin_and_uploads(app)
    
    # 8. 注册全局钩子和错误处理器
    _register_hooks_and_handlers(app)
    
    # 9. 注册SocketIO事件处理器
    _register_socketio_events(app)
    
    # 10. 初始化Celery
    from web import celery_utils
    app.extensions['celery'] = celery_utils.make_celery(app)
    
    return app

# ===== 辅助初始化函数 =====

def _initialize_extensions(app):
    """初始化所有Flask扩展"""
    # 注意：db.init_app 只需要调用一次
    db.init_app(app)
    
    # 迁移扩展
    migrate.init_app(app, db)
    
    # 会话管理
    Session(app)
    
    # SocketIO配置
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
    
    # CSRF保护
    csrf.init_app(app)
    
    # 登录管理
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

def _check_database_version(app):
    """检查数据库迁移版本"""
    from sqlalchemy import inspect
    
    inspector = inspect(db.engine)
    if 'alembic_version' in inspector.get_table_names():
        try:
            result = db.session.execute('SELECT version_num FROM alembic_version').first()
            if not result:
                print("[FATAL] 数据库版本号未检测到，程序终止。", file=sys.stderr)
                sys.exit(101)
            version = result[0]
            print(f"[INFO] 当前数据库版本: {version}")
        except Exception as e:
            print(f"[FATAL] 数据库版本检测异常: {e}", file=sys.stderr)
            sys.exit(102)
    else:
        print("[INFO] 未检测到Alembic版本表，可能是新数据库或未使用迁移。")

def _initialize_services(app, config_class):
    """初始化数据管理和评分服务"""
    # 注意：这些服务依赖于配置，必须在配置加载后初始化
    from web.utils.data_manager import DataManager
    from web.services.grading import GradingService
    
    # 创建服务实例
    data_manager = DataManager(config_class)
    
    # 检查DLL路径是否可用
    dll_path = getattr(config_class, 'DLL_PATH', None)
    if dll_path and os.path.exists(dll_path):
        grading_service = GradingService(dll_path)
        lib = grading_service if grading_service.is_available() else None
    else:
        print(f"[WARN] DLL路径不存在或未配置: {dll_path}")
        lib = None
    
    # 初始化评分队列
    from web.utils.queue_manager import GradingQueue
    num_workers = getattr(config_class, 'GRADING_WORKERS', 4)
    
    with app.app_context():
        grading_queue = GradingQueue(app, data_manager, lib, num_workers=num_workers)
        
        # 将服务实例附加到app，便于蓝图访问
        app.grading_queue = grading_queue
        app.data_manager = data_manager
        
        # 自动建表（如果未跳过）
        if not os.environ.get('SKIP_INIT_DB'):
            db.create_all()
            data_manager.init_db(app)

def _register_blueprints(app):
    """注册所有蓝图（延迟导入避免循环依赖）"""
    # 延迟导入蓝图
    from web.blueprints.auth import auth_bp
    from web.blueprints.main import main_bp
    from web.blueprints.exam import exam_bp
    from web.blueprints.admin import admin_bp
    from web.blueprints.forum import forum_bp
    from web.blueprints.workshop import workshop_bp
    from web.blueprints.workshop_admin import workshop_admin_bp
    from web.blueprints.ai import bp as ai_bp
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(forum_bp)
    app.register_blueprint(workshop_bp)
    app.register_blueprint(workshop_admin_bp)
    app.register_blueprint(ai_bp)

def _initialize_admin_and_uploads(app):
    """初始化管理员界面和上传组件"""
    # Flask-Admin
    from web.admin_view import init_admin
    init_admin(app)
    
    # Flask-Uploads & Flask-Dropzone
    from web.uploads_config import init_uploads
    app.dropzone = init_uploads(app)

def _register_hooks_and_handlers(app):
    """注册全局请求/响应钩子和错误处理器"""
    
    @app.after_request
    def add_header(response):
        """添加安全响应头"""
        # 安全头
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        response.headers['ngrok-skip-browser-warning'] = 'true'
        
        # 缓存控制
        if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        
        # 清理旧头
        response.headers.pop('Pragma', None)
        response.headers.pop('Expires', None)
        
        # 确保字符集
        ct = response.headers.get('Content-Type')
        if ct and 'charset' not in ct.lower():
            if ct.startswith('text/') or ct.startswith('application/json'):
                response.headers['Content-Type'] = ct + '; charset=utf-8'
        
        return response
    
    @app.before_request
    def check_exam_mode():
        """检查考试模式"""
        from flask import session
        if session.get('in_exam'):
            allowed = [
                'exam.exam', 'static', 
                'main.uploaded_file', 
                'exam.waiting', 'exam.queue_status'
            ]
            if request.endpoint in allowed or (
                request.endpoint and request.endpoint.startswith('static')
            ):
                return
            flash('考试进行中，无法访问其他页面！', 'warning')
            return redirect(url_for('exam.exam'))
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

def _register_socketio_events(app):
    """注册SocketIO事件处理器"""
    @socketio.on('join')
    def on_join(data):
        from flask_socketio import join_room
        room = data.get('room')
        if room:
            join_room(room)
            app.logger.debug(f"客户端加入房间: {room}")
    
    @socketio.on('leave')
    def on_leave(data):
        from flask_socketio import leave_room
        room = data.get('room')
        if room:
            leave_room(room)
            app.logger.debug(f"客户端离开房间: {room}")
    
    @socketio.on('connect')
    def on_connect():
        app.logger.debug(f"客户端连接: {request.sid}")
    
    @socketio.on('disconnect')
    def on_disconnect():
        app.logger.debug(f"客户端断开: {request.sid}")
    
    @socketio.on('draft_status')
    def on_draft_status(data):
        app.logger.debug(f"收到草稿状态事件: {data}")