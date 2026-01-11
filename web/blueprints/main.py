import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from web.extensions import db, cache_redis
from web.models import User, SystemSetting, UserCategoryStat, Topic, Post, TopicView
import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
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
        data_manager = getattr(current_app, 'data_manager', None)
        if data_manager:
            stats = data_manager.get_system_stats()
            if cache_redis:
                try:
                    # Cache for 60 seconds
                    cache_redis.setex('system_stats', 60, json.dumps(stats))
                except Exception as e:
                    print(f"Redis cache set error: {e}")

    user_charts = None
    user_stats = None
    if current_user.is_authenticated and not current_user.is_admin:
        data_manager = getattr(current_app, 'data_manager', None)
        if data_manager:
            user_charts = data_manager.get_user_dashboard_stats(current_user.id)
        
        # Calculate Personal Stats for the cards
        ug_stats_query = UserCategoryStat.query.filter_by(user_id=current_user.id).all()
        ug_total_exams = sum(s.total_attempts for s in ug_stats_query)
        ug_total_score = sum(s.total_score for s in ug_stats_query)
        ug_total_max = sum(s.total_max_score for s in ug_stats_query)
        
        # Calculate accuracy
        ug_accuracy = 0
        if ug_total_max > 0:
            ug_accuracy = round((ug_total_score / ug_total_max) * 100, 1)
        
        user_stats = {
            'total_exams': ug_total_exams,
            'avg_accuracy': ug_accuracy
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

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        print(f"[调试] profile视图收到POST: current_password={current_password}, form={dict(request.form)}")

        if not current_user.check_password(current_password):
            print("[调试] 当前密码错误，验证失败")
            flash('当前密码错误，验证失败', 'danger')
            return redirect(url_for('main.profile'))

        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        print(f"[调试] profile视图解析参数: username={username}, email={email}, new_password={new_password}, confirm_password={confirm_password}")

        print(f"[调试] 修改前数据库: 用户名={current_user.username}, 邮箱={current_user.email}, is_admin={current_user.is_admin}")

        # Check username uniqueness if changed
        if username and username != current_user.username:
            existing = User.query.filter_by(username=username).first()
            print(f"[调试] 检查用户名唯一性: username={username}, existing={existing}")
            if existing and existing.id != current_user.id:
                print("[调试] 用户名已被占用，修改失败")
                flash('该用户名已被占用', 'danger')
                return redirect(url_for('main.profile'))
            current_user.username = username
            print(f"[调试] 用户名已变更: {current_user.username}")
        # Update email
        current_user.email = email if email else None
        print(f"[调试] 邮箱已变更: {current_user.email}")
        # Update password
        if new_password:
            if new_password != confirm_password:
                print("[调试] 新密码两次输入不一致，修改失败")
                flash('两次输入的新密码不一致', 'danger')
                return redirect(url_for('main.profile'))
            current_user.set_password(new_password)
            print(f"[调试] 密码已变更，当前 current_user.password_hash={current_user.password_hash}")
        try:
            print(f"[调试] commit前 current_user.password_hash={current_user.password_hash}")
            db.session.commit()
            print(f"[调试] commit已执行")
            db.session.expire_all()
            user_check = User.query.get(current_user.id)
            print(f"[调试] commit后数据库查询(已expire_all): 用户名={user_check.username}, 邮箱={user_check.email}, is_admin={user_check.is_admin}, password_hash={user_check.password_hash}")
            from flask_login import login_user
            login_user(user_check, force=True)
            print(f"[调试] 用户信息已提交: 用户名={user_check.username}, 邮箱={user_check.email}, is_admin={user_check.is_admin}, password_hash={user_check.password_hash}")
            flash('个人资料修改成功', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"[调试] 用户信息提交失败: {e}")
            flash(f'修改失败: {str(e)}', 'danger')
        return redirect(url_for('main.profile'))

    # GET request - Display Profile
    data_manager = getattr(current_app, 'data_manager', None)
    leaderboard = data_manager.get_leaderboard_data() if data_manager else {'global': [], 'categories': {}}
    rank = '未上榜'
    for i, user_stat in enumerate(leaderboard['global']):
        if user_stat['username'] == current_user.username:
            rank = i + 1
            break
    permissions = [p.category for p in current_user.permissions]
    stats_query = UserCategoryStat.query.filter_by(user_id=current_user.id).all()
    total_exams = sum(s.total_attempts for s in stats_query)
    total_score = sum(s.total_score for s in stats_query)
    total_max = sum(s.total_max_score for s in stats_query)
    avg_accuracy = (total_score / total_max * 100) if total_max > 0 else 0
    overall_stats = {
        'total_exams': total_exams,
        'avg_accuracy': avg_accuracy
    }
    my_topics = Topic.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Topic.created_at.desc()).limit(50).all()
    my_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).limit(50).all()
    replies_received = Post.query.join(Topic).filter(
        Topic.user_id == current_user.id,
        Post.user_id != current_user.id
    ).order_by(Post.created_at.desc()).limit(20).all()
    browsing_history = TopicView.query.join(Topic, TopicView.topic_id == Topic.id)\
        .filter(TopicView.user_id == current_user.id)\
        .order_by(TopicView.created_at.desc())\
        .limit(50).all()
    return render_template('profile.html', 
                         rank=rank, 
                         permissions=permissions, 
                         overall_stats=overall_stats,
                         my_topics=my_topics,
                         my_posts=my_posts,
                         replies_received=replies_received,
                         browsing_history=browsing_history)

@main_bp.route('/user/<int:user_id>')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    data_manager = getattr(current_app, 'data_manager', None)
    if data_manager:
        leaderboard = data_manager.get_leaderboard_data()
        rank = '未上榜'
        for i, user_stat in enumerate(leaderboard['global']):
            if user_stat['username'] == user.username:
                rank = i + 1
                break
        stats_query = UserCategoryStat.query.filter_by(user_id=user.id).all()
        total_exams = sum(s.total_attempts for s in stats_query)
        total_score = sum(s.total_score for s in stats_query)
        total_max = sum(s.total_max_score for s in stats_query)
        avg_accuracy = (total_score / total_max * 100) if total_max > 0 else 0.0
        stats = {
            'total_exams': total_exams,
            'avg_accuracy': avg_accuracy
        }
    else:
        rank = 'N/A'
        stats = {'total_exams': 0, 'avg_accuracy': 0}
    topics = Topic.query.filter_by(user_id=user.id, is_deleted=False).order_by(Topic.created_at.desc()).limit(20).all()
    return render_template('user_profile.html', user=user, rank=rank, stats=stats, topics=topics)

@main_bp.route('/leaderboard')
def leaderboard():
    data_manager = getattr(current_app, 'data_manager', None)
    leaderboard = data_manager.get_leaderboard_data() if data_manager else {'global': [], 'categories': {}}
    return render_template('leaderboard.html', leaderboard=leaderboard)

# ================= 工坊相关接口 =====================

# 数据模型（可迁移到 web/models.py）
class WorkshopDraft(db.Model):
    __tablename__ = 'workshop_draft'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    type = db.Column(db.String(32))  # online/file
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = db.relationship('User', backref='workshop_drafts')

@main_bp.route('/workshop/save_draft', methods=['POST'])
@login_required
def save_draft():
    data = request.json
    # TODO: 数据校验与存库
    # title, description, content, type, etc.
    return jsonify({'success': True, 'msg': '草稿已保存', 'data': data})

@main_bp.route('/workshop/upload_file', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    # TODO: 文件类型校验与格式转换
    # 返回txt内容
    return jsonify({'success': True, 'content': '示例txt内容'})

@main_bp.route('/workshop/analyze', methods=['POST'])
@login_required
def analyze():
    text = request.json.get('content', '')
    # TODO: 调用C分析库，返回统计信息
    return jsonify({'success': True, 'stats': {'words': 100, 'sections': 3}})

@main_bp.route('/workshop/my_drafts', methods=['GET'])
@login_required
def my_drafts():
    # TODO: 查询当前用户草稿
    return jsonify({'success': True, 'drafts': []})

@main_bp.route('/workshop/draft/<int:draft_id>', methods=['GET'])
@login_required
def get_draft(draft_id):
    # TODO: 查询草稿详情
    return jsonify({'success': True, 'draft': {}})
# ================= 工坊相关接口 END =====================
