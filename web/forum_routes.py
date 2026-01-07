import os
import uuid
import mimetypes
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Board, Topic, Post, TopicLike
from config import Config

forum_bp = Blueprint('forum', __name__, url_prefix='/forum')

def validate_and_save_forum_image(file):
    if not file or file.filename == '':
        return None, None
        
    ext = ''
    if '.' in file.filename:
        ext = '.' + file.filename.rsplit('.', 1)[1].lower()
    
    is_valid = False
    if ext and ext[1:] in Config.ALLOWED_EXTENSIONS:
        is_valid = True
    elif file.mimetype.startswith('image/'):
        is_valid = True
        if not ext:
            ext = mimetypes.guess_extension(file.mimetype) or '.jpg'
    
    if not is_valid:
        return None, f"不支持的文件类型"
        
    unique_filename = str(uuid.uuid4()) + ext
    # Use the same uploads folder as the main app
    path = os.path.join(current_app.static_folder, 'uploads', unique_filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    return unique_filename, None

# --- Context Processor ---
@forum_bp.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# --- Admin Routes ---
@forum_bp.route('/admin')
@login_required
def admin_index():
    if not current_user.is_admin:
        flash('权限不足', 'danger')
        return redirect(url_for('forum.index'))
    boards = Board.query.order_by(Board.order).all()
    return render_template('forum/admin.html', boards=boards)

@forum_bp.route('/admin/board/new', methods=['POST'])
@login_required
def create_board():
    if not current_user.is_admin:
        return redirect(url_for('forum.index'))
    name = request.form.get('name')
    desc = request.form.get('description')
    order = request.form.get('order', 0)
    
    if name:
        board = Board(name=name, description=desc, order=order)
        db.session.add(board)
        db.session.commit()
        flash('版块创建成功', 'success')
    return redirect(url_for('forum.admin_index'))

@forum_bp.route('/admin/board/<int:board_id>/delete', methods=['POST'])
@login_required
def delete_board(board_id):
    if not current_user.is_admin:
        return redirect(url_for('forum.index'))
    board = Board.query.get_or_404(board_id)
    db.session.delete(board)
    db.session.commit()
    flash('版块已删除', 'success')
    return redirect(url_for('forum.admin_index'))

# --- Public Routes ---
@forum_bp.route('/')
@login_required
def index():
    boards = Board.query.order_by(Board.order).all()
    q = request.args.get('q', '').strip()
    if q:
        # Global search for topics
        topics = Topic.query.filter(Topic.title.ilike(f'%{q}%'), Topic.is_deleted == False)\
            .order_by(Topic.updated_at.desc()).all()
        return render_template('forum/index.html', boards=boards, search_results=topics, search_query=q)
    
    return render_template('forum/index.html', boards=boards)

@forum_bp.route('/board/<int:board_id>')
@login_required
def view_board(board_id):
    board = Board.query.get_or_404(board_id)
    page = request.args.get('page', 1, type=int)
    topics = Topic.query.filter_by(board_id=board_id, is_deleted=False)\
        .order_by(Topic.is_pinned.desc(), Topic.updated_at.desc())\
        .paginate(page=page, per_page=20)
    return render_template('forum/board.html', board=board, topics=topics)

@forum_bp.route('/board/<int:board_id>/new', methods=['GET', 'POST'])
@login_required
def new_topic(board_id):
    if current_user.is_muted:
        flash('您已被禁言，无法发布主题', 'danger')
        return redirect(url_for('forum.view_board', board_id=board_id))
        
    board = Board.query.get_or_404(board_id)
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        images = request.files.getlist('images')
        
        image_filenames = []
        for img in images:
            fname, err = validate_and_save_forum_image(img)
            if fname:
                image_filenames.append(fname)
        
        topic = Topic(
            board_id=board.id,
            user_id=current_user.id,
            title=title,
            content=content,
            images=image_filenames
        )
        db.session.add(topic)
        db.session.commit()
        flash('发布成功', 'success')
        return redirect(url_for('forum.view_topic', topic_id=topic.id))
        
    return render_template('forum/edit_topic.html', board=board, is_new=True)

@forum_bp.route('/topic/<int:topic_id>')
@login_required
def view_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.is_deleted:
        abort(404)
        
    # Increment views (simple)
    topic.views += 1
    db.session.commit()
    
    posts = Post.query.filter_by(topic_id=topic.id).order_by(Post.created_at).all()
    user_liked = False
    if current_user.is_authenticated:
        user_liked = TopicLike.query.filter_by(user_id=current_user.id, topic_id=topic.id).first() is not None
        
    return render_template('forum/topic.html', topic=topic, posts=posts, user_liked=user_liked)

@forum_bp.route('/topic/<int:topic_id>/reply', methods=['POST'])
@login_required
def reply_topic(topic_id):
    if current_user.is_muted:
        flash('您已被禁言，无法发表回复', 'danger')
        return redirect(url_for('forum.view_topic', topic_id=topic_id))

    topic = Topic.query.get_or_404(topic_id)
    if topic.is_locked:
        flash('该主题已被锁定', 'warning')
        return redirect(url_for('forum.view_topic', topic_id=topic.id))
        
    content = request.form.get('content')
    parent_id = request.form.get('parent_id')
    
    # Optional Validation logic for parent_id existence could go here

    if content:
        post = Post(topic_id=topic_id, user_id=current_user.id, content=content)
        if parent_id:
            try:
                post.parent_id = int(parent_id)
            except: pass
            
        db.session.add(post)
        topic.updated_at = datetime.utcnow() # Bump topic
        db.session.commit()
        flash('回复成功', 'success')
        
    return redirect(url_for('forum.view_topic', topic_id=topic.id))

@forum_bp.route('/topic/<int:topic_id>/action', methods=['POST'])
@login_required
def topic_action(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    action = request.form.get('action')
    
    if action == 'like':
        existing = TopicLike.query.filter_by(user_id=current_user.id, topic_id=topic.id).first()
        if existing:
            db.session.delete(existing)
        else:
            like = TopicLike(user_id=current_user.id, topic_id=topic.id)
            db.session.add(like)
        db.session.commit()
        return redirect(request.referrer)
    
    # Admin only actions
    if not current_user.is_admin:
        flash('权限不足', 'danger')
        return redirect(request.referrer)
        
    if action == 'pin':
        topic.is_pinned = not topic.is_pinned
        flash('置顶状态已更新', 'info')
    elif action == 'lock':
        topic.is_locked = not topic.is_locked
        flash('锁定状态已更新', 'info')
    elif action == 'delete':
        topic.is_deleted = True
        flash('主题已删除', 'success')
        db.session.commit()
        return redirect(url_for('forum.view_board', board_id=topic.board_id))
        
    db.session.commit()
    return redirect(request.referrer)

@forum_bp.route('/topic/<int:topic_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.user_id != current_user.id and not current_user.is_admin:
        abort(403)
        
    if request.method == 'POST':
        topic.title = request.form.get('title')
        topic.content = request.form.get('content')
        
        images = request.files.getlist('images')
        current_imgs = topic.images
        for img in images:
            fname, err = validate_and_save_forum_image(img)
            if fname:
                current_imgs.append(fname)
        topic.images = current_imgs
        
        db.session.commit()
        flash('修改成功', 'success')
        return redirect(url_for('forum.view_topic', topic_id=topic.id))
        
    return render_template('forum/edit_topic.html', topic=topic, is_new=False, board=topic.board)
