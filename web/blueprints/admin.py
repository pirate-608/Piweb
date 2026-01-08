import os
import uuid
import mimetypes
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db, data_manager
from models import User, SystemSetting, UserCategoryStat

admin_bp = Blueprint('admin', __name__)

def validate_and_save_image(file):
    """
    Returns: (filename, error_message)
    """
    if not file or file.filename == '':
        return None, None

    ext = ''
    if '.' in file.filename:
        ext = '.' + file.filename.rsplit('.', 1)[1].lower()
    
    is_valid = False
    if ext and ext[1:] in current_app.config['ALLOWED_EXTENSIONS']:
        is_valid = True
    elif file.mimetype.startswith('image/'):
        is_valid = True
        if not ext:
            ext = mimetypes.guess_extension(file.mimetype) or '.jpg'
    
    if not is_valid:
        return None, f"不支持的文件格式 '{file.filename}'"
    
    unique_filename = str(uuid.uuid4()) + ext
    try:
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename, None
    except Exception as e:
        return None, f"保存文件失败: {str(e)}"

@admin_bp.route('/admin/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('main.index'))
    
    q = request.args.get('q', '').strip()
    if q:
        all_users = User.query.filter(User.username.ilike(f'%{q}%')).all()
    else:
        all_users = User.query.all()
        
    user_list = []
    
    for u in all_users:
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

@admin_bp.route('/admin/user/<int:user_id>/action', methods=['POST'])
@login_required
def user_action(user_id):
    if not current_user.is_admin:
        return {'status': 'error', 'msg': 'Unauthorized'}, 403
        
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    
    if user.id == current_user.id:
        flash('无法对自己执行此操作', 'warning')
        return redirect(url_for('admin.users'))

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
    return redirect(url_for('admin.users'))

@admin_bp.route('/admin/user/<int:user_id>')
@login_required
def user_detail(user_id):
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    
    leaderboard = data_manager.get_leaderboard_data()
    rank = '未上榜'
    for i, user_stat in enumerate(leaderboard['global']):
        if user_stat['username'] == user.username:
            rank = i + 1
            break
            
    permissions = [p.category for p in user.permissions]
    
    stats_query = UserCategoryStat.query.filter_by(user_id=user.id).all()
    total_exams = sum(s.total_attempts for s in stats_query)
        
    # Average Score per Exam
    total_score = sum(s.total_score for s in stats_query)
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

@admin_bp.route('/admin/guide/update', methods=['POST'])
@login_required
def update_guide():
    if not current_user.is_admin:
        flash('只有管理员可以编辑用户指南', 'danger')
        return redirect(url_for('main.index'))
        
    content = request.form.get('content')
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
    return redirect(url_for('main.index'))

@admin_bp.route('/admin/announcement/update', methods=['POST'])
@login_required
def update_announcement():
    if not current_user.is_admin:
        flash('只有管理员可以编辑公告', 'danger')
        return redirect(url_for('main.index'))
        
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
    return redirect(url_for('main.index'))

@admin_bp.route('/manage')
@login_required
def manage():
    if not current_user.is_admin:
        flash('您没有权限访问该页面', 'danger')
        return redirect(url_for('main.index'))
        
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

@admin_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    from models import UserPermission
    has_perm = UserPermission.query.filter_by(user_id=current_user.id).first() is not None
    
    if not current_user.is_admin and not has_perm:
        flash('您没有权限访问该页面', 'danger')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        contents = request.form.getlist('content[]')
        answers = request.form.getlist('answer[]')
        scores = request.form.getlist('score[]')
        categories = request.form.getlist('category[]')
        images = request.files.getlist('image[]')
        
        if contents and answers and scores:
            for i, (c, a, s) in enumerate(zip(contents, answers, scores)):
                if c and a and s:
                    cat = categories[i] if i < len(categories) and categories[i] else '默认题集'
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
            return redirect(url_for('admin.manage'))
            
    return render_template('add.html', categories=data_manager.get_categories())

@admin_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_question(id):
    if not current_user.is_admin:
        flash('您没有权限执行此操作', 'danger')
        return redirect(url_for('main.index'))
        
    image_filename = data_manager.delete_question(id)
    if image_filename:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass
    return redirect(url_for('admin.manage'))

@admin_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_question(id):
    if not current_user.is_admin:
        flash('您没有权限执行此操作', 'danger')
        return redirect(url_for('main.index'))
        
    question = data_manager.get_question(id)
    if not question:
        return redirect(url_for('admin.manage'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        answer = request.form.get('answer')
        score = request.form.get('score')
        
        if content and answer and score:
            image_filename = question.get('image', '')
            
            if request.form.get('delete_image') == 'yes':
                if image_filename:
                    old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except:
                            pass
                    image_filename = ''

            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    new_filename, error = validate_and_save_image(file)
                    if error:
                        flash(error, 'danger')
                        return redirect(url_for('admin.edit_question', id=id))
                    
                    if new_filename:
                        if image_filename:
                            old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
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
            return redirect(url_for('admin.manage'))
            
    return render_template('edit.html', question=question, id=id, categories=data_manager.get_categories())

@admin_bp.route('/admin/queue')
@login_required
def queue():
    if not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    return current_app.grading_queue.get_queue_stats()
