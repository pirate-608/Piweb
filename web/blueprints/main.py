import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from extensions import db, data_manager, cache_redis
from models import User, SystemSetting, UserCategoryStat, Topic, Post, TopicView

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
        
        if not current_user.check_password(current_password):
            flash('当前密码错误，验证失败', 'danger')
            return redirect(url_for('main.profile'))
            
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Check username uniqueness if changed
        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                flash('该用户名已被占用', 'danger')
                return redirect(url_for('main.profile'))
            current_user.username = username
            
        # Update email
        current_user.email = email if email else None
        
        # Update password
        if new_password:
            if new_password != confirm_password:
                flash('两次输入的新密码不一致', 'danger')
                return redirect(url_for('main.profile'))
            current_user.set_password(new_password)
            
        try:
            db.session.commit()
            flash('个人资料修改成功', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'修改失败: {str(e)}', 'danger')
            
        return redirect(url_for('main.profile'))

    # GET request - Display Profile
    
    leaderboard = data_manager.get_leaderboard_data()
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

    browsing_history = db.session.query(TopicView, Topic)\
        .join(Topic, TopicView.topic_id == Topic.id)\
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
        total_max = sum(s.total_max_score for s in stats_query)
        
        avg_accuracy = (total_score / total_max * 100) if total_max > 0 else 0.0
        
        stats = {
            'total_exams': total_exams,
            'avg_accuracy': avg_accuracy
        }
    except:
        rank = 'N/A'
        stats = {'total_exams': 0, 'avg_accuracy': 0}
        
    topics = Topic.query.filter_by(user_id=user.id, is_deleted=False).order_by(Topic.created_at.desc()).limit(20).all()
    
    return render_template('user_profile.html', user=user, rank=rank, stats=stats, topics=topics)

@main_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main_bp.route('/leaderboard')
@login_required
def leaderboard():
    data = data_manager.get_leaderboard_data()
    return render_template('leaderboard.html', global_leaderboard=data['global'], category_leaderboards=data['categories'])
