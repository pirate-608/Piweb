import os
import sys
import ctypes
import uuid
import json
import random
import csv
import io
import mimetypes
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from flask_socketio import SocketIO, join_room, leave_room
import redis
import celery_utils
import eventlet

# Patch for better performance (Important for socketio async mode)
# eventlet.monkey_patch() 

from config import Config
from utils.data_manager import DataManager
from utils.queue_manager import GradingQueue
from models import db, User, SystemSetting, UserCategoryStat, Topic, Post

if getattr(sys, 'frozen', False):
    # Determine base directory for resources
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        # Onedir mode, usually in _internal
        base_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
        if not os.path.exists(base_dir):
            base_dir = os.path.dirname(sys.executable)

    template_folder = os.path.join(base_dir, 'templates')
    static_folder = os.path.join(base_dir, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.config.from_object(Config)
db.init_app(app)

# Initialize Flask-Session (Server-side Session)
Session(app)

# Initialize SocketIO with message queue (for Celery communication)
socketio = SocketIO(app, message_queue=app.config.get('CELERY_BROKER_URL'), async_mode='eventlet', cors_allowed_origins='*')

# Initialize Redis Client for Caching (Manual)
try:
    cache_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    # Test connection
    cache_redis.ping()
    print("Redis cache connected.")
except Exception as e:
    print(f"Warning: Redis cache connection failed: {e}")
    cache_redis = None

csrf = CSRFProtect(app)

from forum_routes import forum_bp

app.register_blueprint(forum_bp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

data_manager = DataManager(Config)
if not os.environ.get('SKIP_INIT_DB'):
    data_manager.init_db(app)

# Initialize Celery
if not hasattr(app.extensions, 'celery'):
    app.extensions['celery'] = celery_utils.make_celery(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.after_request
def add_header(response):
    # Security Headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # 尝试解决 ngrok 免费版拦截页面问题 (主要针对 API 调用或特定客户端)
    response.headers['ngrok-skip-browser-warning'] = 'true'
    # 防止浏览器缓存页面 (对于考试页面很重要)
    if 'exam' in request.path:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.before_request
def check_exam_mode():
    # 如果用户处于考试模式
    if session.get('in_exam'):
        # 允许访问的端点：exam (考试页), static (静态资源), uploaded_file (上传的图片)
        # 注意：request.endpoint 在请求静态文件时可能是 'static'
        if request.endpoint in ['exam', 'static', 'uploaded_file']:
            return
        # 其他页面一律重定向回考试页
        flash('考试进行中，无法访问其他页面！', 'warning')
        return redirect(url_for('exam'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def validate_and_save_image(file):
    """
    验证并保存上传的图片文件
    Returns: (filename, error_message)
    """
    if not file or file.filename == '':
        return None, None

    # 1. Check extension
    ext = ''
    if '.' in file.filename:
        ext = '.' + file.filename.rsplit('.', 1)[1].lower()
    
    is_valid = False
    # Check extension against allowed list
    if ext and ext[1:] in Config.ALLOWED_EXTENSIONS:
        is_valid = True
    # Check mimetype as fallback or primary check
    elif file.mimetype.startswith('image/'):
        is_valid = True
        if not ext:
            ext = mimetypes.guess_extension(file.mimetype) or '.jpg'
    
    if not is_valid:
        return None, f"不支持的文件格式 '{file.filename}'。仅支持图片文件 (JPG, PNG, GIF, WebP, SVG, BMP, TIFF)。"
    
    # Generate unique filename
    unique_filename = str(uuid.uuid4()) + ext
    try:
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename, None
    except Exception as e:
        return None, f"保存文件失败: {str(e)}"

# Load C Library
try:
    lib = ctypes.CDLL(Config.DLL_PATH)
    # int calculate_score(const char* user_ans, const char* correct_ans, int full_score);
    lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    lib.calculate_score.restype = ctypes.c_int
    print(f"Successfully loaded DLL from {Config.DLL_PATH}")
except Exception as e:
    print(f"Error loading DLL: {e}")
    lib = None

# Initialize Grading Queue
# Use configured number of workers (default to 4 if not set)
num_workers = getattr(Config, 'GRADING_WORKERS', 4)
grading_queue = GradingQueue(app, data_manager, lib, num_workers=num_workers)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    q = request.args.get('q', '').strip()
    if q:
        users = User.query.filter(User.username.ilike(f'%{q}%')).all()
    else:
        users = User.query.all()
        
    user_list = []
    
    for u in users:
        permissions = [p.category for p in u.permissions]
        user_list.append({
            'id': u.id,
            'username': u.username,
            'is_admin': u.is_admin,
            'is_banned': u.is_banned,
            'is_muted': u.is_muted,
            'permissions': permissions
        })
        
    return render_template('admin_users.html', users=user_list, search_query=q)

@app.route('/admin/user/<int:user_id>/action', methods=['POST'])
@login_required
def admin_user_action(user_id):
    if not current_user.is_admin:
        return {'status': 'error', 'msg': 'Unauthorized'}, 403
        
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    
    if user.id == current_user.id:
        flash('无法对自己执行此操作', 'warning')
        return redirect(url_for('admin_users'))

    if action == 'toggle_ban':
        user.is_banned = not user.is_banned
        msg = f"用户 {user.username} 已{'封禁' if user.is_banned else '解封'}"
    elif action == 'toggle_mute':
        user.is_muted = not user.is_muted
        msg = f"用户 {user.username} 已{'禁言' if user.is_muted else '解除禁言'}"
    else:
        msg = "无效操作"
    
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    # 1. Calculate Rank
    leaderboard = data_manager.get_leaderboard_data()
    rank = '未上榜'
    for i, user_stat in enumerate(leaderboard['global']):
        if user_stat['username'] == user.username:
            rank = i + 1
            break
            
    # 2. Permissions
    permissions = [p.category for p in user.permissions]
    
    # 3. Overall Stats
    stats_query = UserCategoryStat.query.filter_by(user_id=user.id).all()
    total_exams = sum(s.total_attempts for s in stats_query)
    total_score = sum(s.total_score for s in stats_query)
    
    # Average Score per Exam
    avg_score = (total_score / total_exams) if total_exams > 0 else 0
    
    overall_stats = {
        'total_exams': total_exams,
        'avg_score': avg_score
    }
    
    return render_template('admin_user_detail.html', 
                         user=user, 
                         rank=rank, 
                         permissions=permissions, 
                         overall_stats=overall_stats)

@app.route('/')
def index():
    # Use Redis Cache for System Stats (High traffic optimization)
    stats = None
    if cache_redis:
        try:
            cached_stats = cache_redis.get('system_stats')
            if cached_stats:
                stats = json.loads(cached_stats)
        except Exception as e:
            print(f"Redis cache read error: {e}")
    
    if stats is None:
        stats = data_manager.get_system_stats()
        if cache_redis:
            try:
                # Cache for 60 seconds
                cache_redis.setex('system_stats', 60, json.dumps(stats))
            except Exception as e:
                print(f"Redis cache set error: {e}")

    user_charts = None
    user_stats = None
    if current_user.is_authenticated:
        user_charts = data_manager.get_user_dashboard_stats(current_user.id)
        
        # Calculate Personal Stats for the cards
        ug_stats_query = UserCategoryStat.query.filter_by(user_id=current_user.id).all()
        ug_total_exams = sum(s.total_attempts for s in ug_stats_query)
        ug_total_score = sum(s.total_score for s in ug_stats_query)
        ug_avg = round((ug_total_score / ug_total_exams), 1) if ug_total_exams > 0 else 0
        
        user_stats = {
            'total_exams': ug_total_exams,
            'avg_score': ug_avg
        }
    
    # Get user guide and announcement
    try:
        guide_setting = SystemSetting.query.filter_by(key='user_guide').first()
        user_guide = guide_setting.value if guide_setting else None
        
        announcement_setting = SystemSetting.query.filter_by(key='announcement').first()
        announcement = announcement_setting.value if announcement_setting else None
    except:
        user_guide = None
        announcement = None
        
    return render_template('index.html', stats=stats, user_charts=user_charts, 
                         user_stats=user_stats, 
                         user_guide=user_guide, announcement=announcement)

@app.route('/admin/guide/update', methods=['POST'])
@login_required
def update_guide():
    if not current_user.is_admin:
        flash('只有管理员可以编辑用户指南', 'danger')
        return redirect(url_for('index'))
        
    content = request.form.get('content')
    
    # Lazy creation of table if it doesn't exist (simpler for this context)
    try:
        guide_setting = SystemSetting.query.filter_by(key='user_guide').first()
    except:
        db.create_all()
        guide_setting = None

    if not guide_setting:
        guide_setting = SystemSetting(key='user_guide', value=content)
        db.session.add(guide_setting)
    else:
        guide_setting.value = content
        
    db.session.commit()
    flash('用户指南已更新', 'success')
    return redirect(url_for('index'))

@app.route('/admin/announcement/update', methods=['POST'])
@login_required
def update_announcement():
    if not current_user.is_admin:
        flash('只有管理员可以编辑公告', 'danger')
        return redirect(url_for('index'))
        
    content = request.form.get('content')
    
    try:
        announcement_setting = SystemSetting.query.filter_by(key='announcement').first()
    except:
        db.create_all()
        announcement_setting = None

    if not announcement_setting:
        announcement_setting = SystemSetting(key='announcement', value=content)
        db.session.add(announcement_setting)
    else:
        announcement_setting.value = content
        
    db.session.commit()
    flash('系统公告已更新', 'success')
    return redirect(url_for('index'))

@app.route('/user/<int:user_id>')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # 1. Rank & Stats
    try:
        leaderboard = data_manager.get_leaderboard_data()
        rank = '未上榜'
        for i, user_stat in enumerate(leaderboard['global']):
            if user_stat['username'] == user.username:
                rank = i + 1
                break
        
        stats_query = UserCategoryStat.query.filter_by(user_id=user.id).all()
        total_exams = sum(s.total_attempts for s in stats_query)
        total_score = sum(s.total_score for s in stats_query)
        avg_score = (total_score / total_exams) if total_exams > 0 else 0.0
        
        stats = {
            'total_exams': total_exams,
            'avg_score': avg_score
        }
    except:
        rank = 'N/A'
        stats = {'total_exams': 0, 'avg_score': 0}
        
    # 2. Topics
    topics = Topic.query.filter_by(user_id=user.id, is_deleted=False).order_by(Topic.created_at.desc()).limit(20).all()
    
    return render_template('user_profile.html', user=user, rank=rank, stats=stats, topics=topics)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        login_id = request.form.get('username') # Form field is still named username
        password = request.form.get('password')
        
        # Try finding by username first, then email
        user = User.query.filter((User.username == login_id) | (User.email == login_id)).first()
        
        if user and user.check_password(password):
            if user.is_banned:
                flash('该账号已被封禁，无法登录', 'danger')
                return render_template('login.html')
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')
            
    return render_template('login.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        
        if not current_user.check_password(current_password):
            flash('当前密码错误，验证失败', 'danger')
            return redirect(url_for('profile'))
            
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Check username uniqueness if changed
        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                flash('该用户名已被占用', 'danger')
                return redirect(url_for('profile'))
            current_user.username = username
            
        # Update email
        current_user.email = email if email else None
        
        # Update password
        if new_password:
            if new_password != confirm_password:
                flash('两次输入的新密码不一致', 'danger')
                return redirect(url_for('profile'))
            current_user.set_password(new_password)
            
        try:
            db.session.commit()
            flash('个人资料修改成功', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'修改失败: {str(e)}', 'danger')
            
        return redirect(url_for('profile'))

    # GET request - Display Profile
    
    # 1. Calculate Rank
    leaderboard = data_manager.get_leaderboard_data()
    rank = '未上榜'
    for i, user_stat in enumerate(leaderboard['global']):
        if user_stat['username'] == current_user.username:
            rank = i + 1
            break
            
    # 2. Permissions
    permissions = [p.category for p in current_user.permissions]
    
    # 3. Overall Stats
    stats_query = UserCategoryStat.query.filter_by(user_id=current_user.id).all()
    total_exams = sum(s.total_attempts for s in stats_query)
    total_score = sum(s.total_score for s in stats_query)
    # Average Score per Exam
    avg_score = (total_score / total_exams) if total_exams > 0 else 0
    
    overall_stats = {
        'total_exams': total_exams,
        'avg_score': avg_score
    }
    
    # New: Forum Data
    my_topics = Topic.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Topic.created_at.desc()).limit(50).all()
    my_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).limit(50).all()
    
    replies_received = Post.query.join(Topic).filter(
        Topic.user_id == current_user.id,
        Post.user_id != current_user.id
    ).order_by(Post.created_at.desc()).limit(20).all()
    
    return render_template('profile.html', 
                         rank=rank, 
                         permissions=permissions, 
                         overall_stats=overall_stats,
                         my_topics=my_topics,
                         my_posts=my_posts,
                         replies_received=replies_received)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('register'))
            
        if data_manager.create_user(username, password):
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        else:
            flash('用户名已存在', 'danger')
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/manage')
@login_required
def manage():
    if not current_user.is_admin:
        flash('您没有权限访问该页面', 'danger')
        return redirect(url_for('index'))
        
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    pagination = data_manager.get_questions_paginated(page=page, per_page=10, search=search, category=category)
    categories = data_manager.get_categories()
    
    return render_template('manage.html', 
                         questions=pagination.items, 
                         pagination=pagination,
                         search=search,
                         current_category=category,
                         categories=categories)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_question(id):
    if not current_user.is_admin:
        flash('您没有权限执行此操作', 'danger')
        return redirect(url_for('index'))
        
    image_filename = data_manager.delete_question(id)
    # Delete image file if exists
    if image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass
    return redirect(url_for('manage'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_question(id):
    if not current_user.is_admin:
        flash('您没有权限执行此操作', 'danger')
        return redirect(url_for('index'))
        
    question = data_manager.get_question(id)
    if not question:
        return redirect(url_for('manage'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        answer = request.form.get('answer')
        score = request.form.get('score')
        
        if content and answer and score:
            image_filename = question.get('image', '')
            
            # Handle delete image
            if request.form.get('delete_image') == 'yes':
                if image_filename:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except:
                            pass
                    image_filename = ''

            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    new_filename, error = validate_and_save_image(file)
                    if error:
                        flash(error, 'danger')
                        return redirect(url_for('edit_question', id=id))
                    
                    if new_filename:
                        # Delete old image if exists (and not already deleted above)
                        if image_filename:
                            old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                            if os.path.exists(old_image_path):
                                try:
                                    os.remove(old_image_path)
                                except:
                                    pass
                        image_filename = new_filename

            data_manager.update_question(
                id,
                content=content,
                answer=answer,
                score=int(score),
                image=image_filename,
                category=request.form.get('category', '默认题集')
            )
            return redirect(url_for('manage'))
            
    return render_template('edit.html', question=question, id=id, categories=data_manager.get_categories())

@app.route('/select_set')
@login_required
def select_set():
    questions = data_manager.load_questions()
    if not questions:
        flash('题库为空，请先添加题目！', 'warning')
        return redirect(url_for('index'))
        
    # Count questions per category
    categories = {}
    for q in questions:
        cat = q.get('category', '默认题集')
        categories[cat] = categories.get(cat, 0) + 1
        
    return render_template('select_set.html', categories=categories, total_count=len(questions))

@app.route('/start_exam')
@login_required
def start_exam():
    # Redirect to selection page first
    return redirect(url_for('select_set'))

@app.route('/exam', methods=['GET', 'POST'])
@login_required
def exam():
    # Check if category is selected via GET param (first entry)
    category = request.args.get('category')
    
    # If starting new exam
    if request.method == 'GET' and not session.get('in_exam'):
        if not category:
            return redirect(url_for('select_set'))
        session['in_exam'] = True
        session['start_time'] = datetime.now().timestamp()
        session['exam_category'] = category # Store selected category

    # Security check
    if not session.get('in_exam'):
        return redirect(url_for('index'))

    all_questions = data_manager.load_questions()
    
    # Filter questions based on session category
    current_category = session.get('exam_category', 'all')
    if current_category != 'all':
        filtered_ids = [q['id'] for q in all_questions if q.get('category', '默认题集') == current_category]
    else:
        filtered_ids = [q['id'] for q in all_questions]

    if not filtered_ids:
        session.pop('in_exam', None)
        flash('该题集没有题目！', 'warning')
        return redirect(url_for('select_set'))

    if request.method == 'GET':
        # Shuffle the filtered indices
        random.shuffle(filtered_ids)
        session['exam_ids'] = filtered_ids
        
        # Retrieve question objects for the IDs
        shuffled_questions = [q for q in all_questions if q['id'] in filtered_ids]
        # Sort them to match the shuffled order in session['exam_ids']
        shuffled_questions.sort(key=lambda x: filtered_ids.index(x['id']))
        
        # Calculate remaining time
        start_time = session.get('start_time', datetime.now().timestamp())
        duration_sec = app.config['EXAM_DURATION_MINUTES'] * 60
        elapsed = datetime.now().timestamp() - start_time
        remaining_sec = max(0, int(duration_sec - elapsed))
        
        return render_template('exam.html', questions=shuffled_questions, remaining_sec=remaining_sec)

    if request.method == 'POST':
        # 获取随机化后的ID列表
        ids = session.get('exam_ids')
        if not ids:
             # Fallback if session lost
             return redirect(url_for('index'))
             
        # Collect answers for queue
        user_answers = {}
        for i, q_id in enumerate(ids):
             user_answers[str(i)] = request.form.get(f'q_{i}', '')
        
        exam_data = {
            'ids': ids,
            'user_answers': user_answers,
            'all_questions': all_questions
        }
        
        # Add to queue
        task_id = grading_queue.add_task(current_user.id, exam_data)

        # 考试结束，清除会话状态
        session.pop('in_exam', None)
        session.pop('exam_ids', None)
        
        return redirect(url_for('waiting', task_id=task_id))
    
    return redirect(url_for('index'))

@app.route('/history')
@login_required
def history():
    # If admin, show all results; otherwise show only own results
    user_id = None if current_user.is_admin else current_user.id
    results = data_manager.load_results(user_id=user_id)
    # Sort by timestamp descending
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    
    q = request.args.get('q', '').strip()
    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in str(r.get('username', '')).lower() or q_lower in str(r.get('timestamp', '')).lower()]
        
    return render_template('history.html', results=results, search_query=q)

@app.route('/leaderboard')
@login_required
def leaderboard():
    data = data_manager.get_leaderboard_data()
    return render_template('leaderboard.html', global_leaderboard=data['global'], category_leaderboards=data['categories'])

@app.route('/export_history')
@login_required
def export_history():
    user_id = None if current_user.is_admin else current_user.id
    results = data_manager.load_results(user_id=user_id)
    # Sort by timestamp descending
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['用户', '时间', '得分', '满分', '得分率'])
    
    for r in results:
        score = r.get('total_score', 0)
        max_s = r.get('max_score', 0)
        percentage = f"{(score / max_s * 100):.1f}%" if max_s > 0 else "0.0%"
        username = r.get('username', 'Unknown')
        writer.writerow([username, r['timestamp'], score, max_s, percentage])
        
    output.seek(0)
    
    return Response(
        output.getvalue().encode('utf-8-sig'), # BOM for Excel
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=exam_history.csv"}
    )

@app.route('/history/delete/<result_id>', methods=['POST'])
@login_required
def delete_history(result_id):
    # Check permission: admin can delete any, user can only delete own
    record = data_manager.get_result(result_id)
    if not record:
        flash('记录未找到', 'error')
        return redirect(url_for('history'))
        
    if not current_user.is_admin and record.get('user_id') != current_user.id:
        flash('您没有权限删除此记录', 'danger')
        return redirect(url_for('history'))

    data_manager.delete_result(result_id)
    flash('记录已删除', 'success')
    return redirect(url_for('history'))

@app.route('/waiting/<task_id>')
@login_required
def waiting(task_id):
    return render_template('waiting.html', task_id=task_id)

@app.route('/queue/status/<task_id>')
@login_required
def queue_status(task_id):
    status = grading_queue.get_status(task_id)
    if not status:
        return {'status': 'error', 'error': 'Task not found'}, 404
    return status

@app.route('/admin/queue')
@login_required
def admin_queue():
    if not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    return grading_queue.get_queue_stats()

@app.route('/history/view/<result_id>')
@login_required
def view_history(result_id):
    record = data_manager.get_result(result_id)
    if not record:
        flash('记录未找到', 'error')
        return redirect(url_for('history'))
        
    if not current_user.is_admin and record.get('user_id') != current_user.id:
        flash('您没有权限查看此记录', 'danger')
        return redirect(url_for('history'))
        
    return render_template('result.html', total_score=record['total_score'], results=record['details'], is_history=True)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    # Check if user is admin or has any permission
    from models import UserPermission
    has_perm = UserPermission.query.filter_by(user_id=current_user.id).first() is not None
    
    if not current_user.is_admin and not has_perm:
        flash('您没有权限访问该页面', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Handle list of values
        contents = request.form.getlist('content[]')
        answers = request.form.getlist('answer[]')
        scores = request.form.getlist('score[]')
        categories = request.form.getlist('category[]')
        images = request.files.getlist('image[]')
        
        if contents and answers and scores:
            for i, (c, a, s) in enumerate(zip(contents, answers, scores)):
                if c and a and s:
                    cat = categories[i] if i < len(categories) and categories[i] else '默认题集'
                    
                    # Check permission for this specific category
                    if not current_user.is_admin:
                        if not data_manager.check_permission(current_user.id, cat):
                            flash(f'您没有权限添加 "{cat}" 类别的题目', 'danger')
                            continue

                    image_filename = ''
                    if i < len(images):
                        file = images[i]
                        filename, error = validate_and_save_image(file)
                        if error:
                            flash(f'第 {i+1} 题图片上传失败: {error}', 'warning')
                        elif filename:
                            image_filename = filename
                    
                    data_manager.save_question(c, a, int(s), image_filename, cat)
            
            flash('题目添加处理完成！', 'success')
            return redirect(url_for('manage'))
            
    return render_template('add.html', categories=data_manager.get_categories())

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Disable debug mode in production/packaged environment
    debug_mode = not getattr(sys, 'frozen', False)
    # Use socketio.run for WebSocket capability
    socketio.run(app, debug=debug_mode, port=5000)

# SocketIO Event Handlers
@socketio.on('join')
def on_join(data):
    """
    Client joins a room named after the task_id.
    """
    room = data.get('room')
    if room:
        join_room(room)
        # print(f"Client joined room: {room}")

