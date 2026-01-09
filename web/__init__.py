import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, redirect, url_for, flash, request, render_template
from web.extensions import db, login_manager, csrf, socketio, cache_redis, data_manager, grading_service
from config import Config
import celery_utils
import logging
from web.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.main import main_bp
from blueprints.exam import exam_bp
from blueprints.admin import admin_bp
from blueprints.forum import forum_bp

def create_app(config_class=Config):
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
    # Session(app) is initialized inside extensions? No, Session() takes app.
    # We didn't move Session to extensions.py because it doesn't need to be imported by blueprints directly.
    # But wait, app.py had: Session(app).
    from flask_session import Session
    Session(app)
    
    socketio.init_app(app, message_queue=app.config.get('CELERY_BROKER_URL'), async_mode='eventlet', cors_allowed_origins='*')
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Updated to blueprint endpoint

    # Initialize Data Manager DB
    if not os.environ.get('SKIP_INIT_DB'):
        with app.app_context():
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
    
    # Attach queue to app so blueprints can access it
    app.grading_queue = grading_queue

    # Initialize Celery
    app.extensions['celery'] = celery_utils.make_celery(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(forum_bp) # url_prefix='/forum' defined in blueprint

    # Register Global Hooks
    @app.after_request
    def add_header(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['ngrok-skip-browser-warning'] = 'true'
        if 'exam' in request.path:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
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
        if room:
            join_room(room)

    return app
