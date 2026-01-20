from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user
from web.extensions import db
from web.models import WorkshopWork, SystemSetting
import math, json

# 权限装饰器（必须在所有@admin_required之前）
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify(success=False, msg='权限不足'), 403
        return func(*args, **kwargs)
    return wrapper

workshop_admin_bp = Blueprint('workshop_admin', __name__, url_prefix='/workshop/admin')

# 管理后台作品全量/搜索API
@workshop_admin_bp.route('/api/works', methods=['GET'])
@login_required
@admin_required
def admin_api_works():
    # 支持关键词搜索和分页
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))
    keyword = request.args.get('keyword')
    query = WorkshopWork.query
    if keyword:
        like_expr = f"%{keyword}%"
        query = query.filter(
            (WorkshopWork.title.ilike(like_expr)) |
            (WorkshopWork.description.ilike(like_expr)) |
            (WorkshopWork.keywords.ilike(like_expr))
        )
    query = query.order_by(WorkshopWork.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    works = []
    for w in pagination.items:
        works.append({
            'id': w.id,
            'title': w.title,
            'author': w.user.username if w.user else '',
            'description': w.description,
            'theme': w.theme,
            'created_at': w.created_at.strftime('%Y-%m-%d %H:%M'),
            'views': w.views,
            'likes': w.likes,
            'is_collab': w.is_collab,
            'keywords': w.keywords,
            'hotness': w.hotness
        })
    return jsonify(success=True, total=pagination.total, page=page, per_page=per_page, works=works)




# 管理后台首页
@workshop_admin_bp.route('/', methods=['GET'])
@login_required
@admin_required
def admin_dashboard():
    return render_template('workshop/admin_dashboard.html')

# 热度参数GET接口（前端联调用）
@workshop_admin_bp.route('/config/hotness', methods=['GET'])
@login_required
@admin_required
def get_hotness_config():
    setting = SystemSetting.query.get('workshop_hotness_weights')
    if setting and setting.value:
        weights = json.loads(setting.value)
    else:
        weights = {'w1': 0.2, 'w2': 1.2, 'g': 1.5}
    return jsonify(success=True, weights=weights)

# 热度参数获取

def get_hotness_weights():
    setting = SystemSetting.query.get('workshop_hotness_weights')
    if setting and setting.value:
        return json.loads(setting.value)
    return {'w1': 0.2, 'w2': 1.2, 'g': 1.5}

def calculate_work_hotness(work, weights=None):
    if not weights:
        weights = get_hotness_weights()
    views = work.views or 0
    likes = work.likes or 0
    now = work.updated_at or work.created_at
    hours = ( (current_app.utcnow() if hasattr(current_app, 'utcnow') else __import__('datetime').datetime.utcnow()) - work.created_at ).total_seconds() / 3600
    view_score = math.log10(views + 1) * weights['w1']
    like_score = likes * weights['w2']
    time_factor = (hours + 2) ** weights['g']
    score = (view_score + like_score) / time_factor
    return score

# 永久删除作品
@workshop_admin_bp.route('/works/<int:work_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_work(work_id):
    try:
        work = WorkshopWork.query.get(work_id)
        if not work:
            return jsonify(success=False, msg='作品不存在'), 404
        db.session.delete(work)
        db.session.commit()
        return jsonify(success=True, msg='已删除')
    except Exception as e:
        current_app.logger.error(f"删除作品异常: {e}")
        return jsonify(success=False, msg='删除失败，服务器异常'), 500

# 切换协作/个人模式
@workshop_admin_bp.route('/works/<int:work_id>/toggle_mode', methods=['POST'])
@login_required
@admin_required
def toggle_mode(work_id):
    work = WorkshopWork.query.get_or_404(work_id)
    work.is_collab = not work.is_collab
    work.pub_type = 'collab' if work.is_collab else 'personal'
    db.session.commit()
    return jsonify(success=True, msg='模式已切换', is_collab=work.is_collab)

# 更改热度参数
@workshop_admin_bp.route('/config/hotness', methods=['POST'])
@login_required
@admin_required
def update_hotness_config():
    try:
        w1 = float(request.form.get('w1', 0.2))
        w2 = float(request.form.get('w2', 1.2))
        g = float(request.form.get('g', 1.5))
        weights = {'w1': w1, 'w2': w2, 'g': g}
        setting = SystemSetting.query.get('workshop_hotness_weights')
        if not setting:
            setting = SystemSetting(key='workshop_hotness_weights')
            db.session.add(setting)
        setting.value = json.dumps(weights, ensure_ascii=False)
        db.session.commit()
        return jsonify(success=True, msg='热度参数已更新')
    except Exception as e:
        return jsonify(success=False, msg=str(e)), 400

# 手动刷新热度
@workshop_admin_bp.route('/update_hotness', methods=['POST'])
@login_required
@admin_required
def update_hotness():
    from web.models import User, StardustHistory
    works = WorkshopWork.query.all()
    weights = get_hotness_weights()
    # 热度档位设置（等比递增）
    hotness_levels = [10, 30, 60, 120, 240, 480, 960, 1920]
    alpha = 0.5  # 奖励系数
    beta = 10    # 最低奖励
    user_count = User.query.count() or 1
    import math
    count = 0
    for w in works:
        old_hotness = w.hotness
        w.hotness = calculate_work_hotness(w, weights)
        # 检查是否跨越新档位
        milestone = w.hotness_milestone or 0
        next_level = milestone
        while next_level < len(hotness_levels) and w.hotness >= hotness_levels[next_level]:
            next_level += 1
        if next_level > milestone and w.user_id:
            # 依次发放每个新达成档位的奖励
            for i in range(milestone, next_level):
                H = hotness_levels[i]
                S = max(int(alpha * H * math.log2(user_count + 1)), beta)
                user = User.query.get(w.user_id)
                if user:
                    user.stardust = (user.stardust or 0) + S
                    db.session.add(StardustHistory(
                        user_id=user.id,
                        category='workshop',
                        amount=S,
                        reason='workshop_hotness_milestone'
                    ))
            w.hotness_milestone = next_level
        count += 1
    db.session.commit()
    return jsonify(success=True, msg=f'已更新{count}个作品热度并发放奖励')
