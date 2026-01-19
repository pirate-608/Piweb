from web.tasks import save_draft_task
from web.extensions import csrf
from flask import Blueprint, current_app, abort, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from web.extensions import db
from web.models import WorkshopDraft, WorkshopWork, WorkshopWorkEditHistory, User
from web.services.analyzer import AnalyzerService
from datetime import datetime, timedelta
import hashlib
import json
from typing import Optional, Dict, Any, List, Union
from functools import wraps

# 只定义一个 Blueprint 实例
workshop_bp = Blueprint('workshop', __name__, url_prefix='/workshop')

# ========== 工坊相关接口（原 main.py 设计风格） ========== #

@workshop_bp.route('/api/draft', methods=['POST', 'GET'])
@login_required
def api_draft():
    """工坊草稿API：POST保存，GET列表"""
    from web.tasks import save_draft_task
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        content = (data.get('content') or '').strip()
        description = (data.get('description') or '').strip()
        draft_type = (data.get('type') or 'online').strip()
        work_id = data.get('work_id')
        if not title or not content:
            return jsonify(success=False, msg='标题和正文不能为空', data=None), 400
        # 先查找/创建草稿，优先用work_id+user_id唯一性
        query = WorkshopDraft.query.filter_by(user_id=current_user.id)
        if work_id:
            query = query.filter_by(work_id=work_id)
        else:
            query = query.filter_by(title=title)
        draft = query.first()
        if not draft:
            draft = WorkshopDraft(
                user_id=current_user.id,
                work_id=work_id,
                title=title,
                description=description,
                content=content,
                type=draft_type
            )
            db.session.add(draft)
            db.session.commit()
        draft_id = draft.id
        # 保持原有推送机制，参数顺序不变，work_id作为kwargs传递
        task = save_draft_task.apply_async(args=[current_user.id, title, content, description, draft_type], kwargs={'work_id': work_id})
        return jsonify(success=True, msg='草稿保存中', data={'task_id': task.id, 'draft_id': draft_id})
    # GET: 查询当前用户所有草稿
    drafts = WorkshopDraft.query.filter_by(user_id=current_user.id).order_by(WorkshopDraft.updated_at.desc()).all()
    draft_list = [
        {
            'id': d.id,
            'title': (d.title or '').strip(),
            'description': (d.description or '').strip(),
            'content': (d.content or '').strip(),
            'type': (getattr(d, 'type', '') or '').strip(),
            'updated_at': d.updated_at.isoformat() if d.updated_at else None,
        } for d in drafts
    ]
    return jsonify(success=True, msg='草稿列表获取成功', data={'drafts': draft_list})

@workshop_bp.route('/save_draft_status', methods=['GET'])
@login_required
def save_draft_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'msg': '缺少task_id'}), 400
    from celery.result import AsyncResult
    celery_app = current_app.extensions['celery']
    result = AsyncResult(task_id, app=celery_app)
    if result.state == 'PENDING':
        return jsonify({'success': False, 'status': 'pending'})
    elif result.state == 'SUCCESS':
        return jsonify({'success': True, 'status': 'done', 'result': result.result})
    elif result.state == 'FAILURE':
        return jsonify({'success': False, 'status': 'error', 'msg': str(result.result)})
    else:
        return jsonify({'success': False, 'status': result.state})

@workshop_bp.route('/upload_file', methods=['POST'])
@csrf.exempt
@login_required
def upload_file():
    import sys
    print(f"[DEBUG] upload_file called: user={{getattr(current_user, 'id', None)}}, files={{request.files}}", file=sys.stderr)
    sys.stderr.flush()
    from werkzeug.utils import secure_filename
    import os
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'msg': '未选择文件'}), 400
    allowed_ext = {'txt', 'md', 'pdf', 'docx'}
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_ext:
        return jsonify({'success': False, 'msg': '文件类型不支持'}), 400
    base_upload_dir = os.path.join(os.path.dirname(__file__), '../static/uploads')
    files_dir = os.path.join(base_upload_dir, 'files')
    os.makedirs(files_dir, exist_ok=True)
    save_path = os.path.join(files_dir, filename)
    file.save(save_path)
    content = ''
    try:
        if ext in {'txt', 'md'}:
            with open(save_path, encoding='utf-8', errors='ignore') as f:
                content = f.read()
        elif ext == 'pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(save_path)
            content = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif ext == 'docx':
            from docx import Document
            doc = Document(save_path)
            content = '\n'.join([para.text for para in doc.paragraphs])
    except Exception as e:
        return jsonify({'success': False, 'msg': f'内容提取失败: {str(e)}'}), 500
    return jsonify({'success': True, 'filename': filename, 'url': f'/static/uploads/{filename}', 'content': content})

@workshop_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    print("Analyzer route called")
    text = request.json.get('content', '')
    from web.services.analyzer import AnalyzerService
    from web.config import Config
    dll_path = Config.LIBANALYZER_PATH
    try:
        analyzer = AnalyzerService(dll_path)
        stats = analyzer.analyze(text)
        print(f"Analyzer stats: {stats}")
    except Exception as e:
        import traceback
        print(f"Analyzer route exception: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'msg': str(e)})
    if not stats.get('ok'):
        print(f"Analyzer failed: {stats.get('msg', '分析失败')}")
        return jsonify({'success': False, 'msg': stats.get('msg', '分析失败')})
    return jsonify({'success': True, 'stats': stats})


@workshop_bp.route('/draft/<int:draft_id>', methods=['GET'])
@login_required
def get_draft(draft_id):
    draft = WorkshopDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()
    if not draft:
        return jsonify({'success': False, 'msg': '草稿不存在'}), 404
    data = {
        'id': draft.id,
        'title': draft.title,
        'description': draft.description,
        'content': draft.content,
        'type': getattr(draft, 'type', ''),
        'updated_at': draft.updated_at.strftime('%Y-%m-%d %H:%M'),
    }
    return jsonify({'success': True, 'draft': data})

@workshop_bp.route('/editor', methods=['GET'])
@login_required
def workshop_editor():
    return render_template('workshop/editor.html')


def _is_collab_work(work: WorkshopWork) -> bool:
    """判断是否为协作作品，兼容多种存储类型"""
    val = work.is_collab
    # 只要不是严格的 False/0/'false'/'no'/'n'/'0' 都判为协作
    if val is None:
        return False
    if isinstance(val, bool):
        return val is True
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() not in ('', '0', 'false', 'no', 'n', 'off')
    return bool(val)


def _validate_json_content(content: str, min_richness: int = 5, max_sensitive: int = 3) -> tuple[bool, str, Dict[str, Any]]:
    """验证JSON内容，返回(是否通过, 错误信息, 分析结果)"""
    try:
        analyzer = AnalyzerService(current_app.config.get('LIBANALYZER_PATH', ''))
        stats = analyzer.analyze(content) or {}
        
        richness = int(stats.get('richness', 0))
        sensitive_words = stats.get('sensitive_words', [])
        
        # 处理可能的字符串格式
        if isinstance(sensitive_words, str):
            try:
                sensitive_words = json.loads(sensitive_words)
            except (json.JSONDecodeError, TypeError):
                sensitive_words = []
        
        sensitive_count = len([w for w in sensitive_words if w])
        
        if richness < min_richness:
            return False, f'内容丰富度不足，需≥{min_richness}，当前为{richness}', stats
        if sensitive_count > max_sensitive:
            return False, f'敏感词过多，需≤{max_sensitive}，当前为{sensitive_count}', stats
            
        return True, '', stats
    except Exception as e:
        current_app.logger.error(f"内容分析失败: {str(e)}")
        return False, '内容分析失败，请稍后重试', {}


def _get_pagination_params() -> tuple[int, int]:
    """安全获取分页参数"""
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = max(1, min(100, int(request.args.get('per_page', 12))))  # 限制每页最大100条
        return page, per_page
    except (ValueError, TypeError):
        return 1, 12


def _build_cache_key() -> str:
    """构建缓存键"""
    page, per_page = _get_pagination_params()
    params = {
        'page': page,
        'per_page': per_page,
        'theme': request.args.get('theme', ''),
        'keyword': request.args.get('keyword', ''),
        'sort': request.args.get('sort', 'latest'),
        'is_collab': request.args.get('is_collab', '')
    }
    cache_key_raw = ':'.join(f"{k}:{v}" for k, v in sorted(params.items()))
    return 'works_api:' + hashlib.md5(cache_key_raw.encode('utf-8')).hexdigest()


def _get_redis_client():
    """获取 Redis 客户端，避免循环依赖"""
    if hasattr(current_app, 'redis_client'):
        return current_app.redis_client
    
    try:
        import redis
        from redis.exceptions import RedisError
        
        redis_config = {
            'host': current_app.config.get('REDIS_HOST', 'localhost'),
            'port': current_app.config.get('REDIS_PORT', 6379),
            'db': current_app.config.get('REDIS_DB', 0),
            'password': current_app.config.get('REDIS_PASSWORD'),
            'decode_responses': True,
            'socket_timeout': current_app.config.get('REDIS_SOCKET_TIMEOUT', 5),
            'socket_connect_timeout': current_app.config.get('REDIS_CONNECT_TIMEOUT', 5)
        }
        
        # 移除None值
        redis_config = {k: v for k, v in redis_config.items() if v is not None}
        
        redis_client = redis.Redis(**redis_config)
        # 测试连接
        redis_client.ping()
        current_app.redis_client = redis_client
        return redis_client
    except (ImportError, RedisError, ConnectionError) as e:
        current_app.logger.warning(f"Redis连接失败: {str(e)}，将使用无缓存模式")
        return None


@workshop_bp.route('/api/works/<int:work_id>/lock', methods=['POST'])
@login_required
def api_work_lock(work_id: int):
    """加锁API"""
    try:
        # CSRF token校验（如有）
        csrf_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token') or request.args.get('csrf_token')
        if hasattr(current_app, 'csrf_token') and callable(current_app.csrf_token):
            if not csrf_token or not current_app.csrf_token.validate(csrf_token):
                return jsonify(success=False, msg='CSRF校验失败'), 400

        work = WorkshopWork.query.get_or_404(work_id)
        if not _is_collab_work(work):
            return jsonify(success=False, msg='仅协作作品可加锁'), 400

        now = datetime.utcnow()
        lock_timeout = timedelta(minutes=30)

        # 检查是否已有有效锁
        if work.edit_lock_user_id and work.edit_lock_time:
            if now - work.edit_lock_time < lock_timeout:
                if work.edit_lock_user_id == current_user.id:
                    return jsonify(success=True, msg='你已获得编辑锁')
                else:
                    lock_user = User.query.get(work.edit_lock_user_id)
                    username = lock_user.username if lock_user else "其他用户"
                    return jsonify(success=False, msg=f'当前有其他人正在编辑：{username}'), 409
            else:
                # 锁已超时，清除旧锁
                work.edit_lock_user_id = None
                work.edit_lock_time = None

        # 加锁
        work.edit_lock_user_id = current_user.id
        work.edit_lock_time = now
        db.session.commit()

        return jsonify(success=True, msg='获得编辑锁')
    except Exception as e:
        current_app.logger.error(f"加锁失败: {str(e)}")
        db.session.rollback()
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/api/works/<int:work_id>/unlock', methods=['POST'])
@login_required
def api_work_unlock(work_id: int):
    """解锁API"""
    try:
        work = WorkshopWork.query.get_or_404(work_id)
        
        if not _is_collab_work(work):
            return jsonify(success=False, msg='仅协作作品可解锁'), 400
        
        # 权限检查
        if work.edit_lock_user_id != current_user.id and not getattr(current_user, 'is_admin', False):
            return jsonify(success=False, msg='无权解锁'), 403
        
        # 解锁
        work.edit_lock_user_id = None
        work.edit_lock_time = None
        db.session.commit()
        
        return jsonify(success=True, msg='已解锁')
    except Exception as e:
        current_app.logger.error(f"解锁失败: {str(e)}")
        db.session.rollback()
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/api/works/<int:work_id>/edit', methods=['POST'])
@login_required
def api_work_edit(work_id: int):
    """编辑提交API"""
    try:
        work = WorkshopWork.query.get_or_404(work_id)
        
        if not _is_collab_work(work):
            return jsonify(success=False, msg='仅协作作品可编辑'), 400
        
        # 检查编辑锁
        if work.edit_lock_user_id != current_user.id:
            return jsonify(success=False, msg='你未获得编辑锁'), 403
        
        # 解析请求数据
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        content = (data.get('content') or '').strip()
        description = (data.get('description') or '').strip()
        is_anonymous = bool(data.get('is_anonymous'))
        agree_protocol = bool(data.get('agree_protocol'))
        
        # 基础验证
        if not title:
            return jsonify(success=False, msg='标题不能为空'), 400
        if not content:
            return jsonify(success=False, msg='内容不能为空'), 400
        if len(title) > 200:  # 限制标题长度
            return jsonify(success=False, msg='标题过长，最多200字符'), 400
        if not agree_protocol:
            return jsonify(success=False, msg='请同意协议'), 400
        
        # 内容审核
        is_valid, error_msg, stats = _validate_json_content(content)
        if not is_valid:
            return jsonify(success=False, msg=error_msg), 400
        
        # 记录历史
        history = WorkshopWorkEditHistory(
            work_id=work.id,
            user_id=current_user.id,
            is_anonymous=is_anonymous,
            edit_time=datetime.utcnow(),
            old_content=work.content,
            new_content=content,
            summary=f"{current_user.username if not is_anonymous else '匿名'}于{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}提交更改"
        )
        db.session.add(history)
        
        # 更新作品内容
        work.title = title
        work.content = content
        work.description = description
        work.updated_at = datetime.utcnow()
        
        # 解锁
        work.edit_lock_user_id = None
        work.edit_lock_time = None
        
        db.session.commit()
        
        return jsonify(success=True, msg='更改已提交并生效')
    except Exception as e:
        current_app.logger.error(f"编辑提交失败: {str(e)}")
        db.session.rollback()
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/api/works/<int:work_id>/history', methods=['GET'])
def api_work_history(work_id: int):
    """编辑历史查询API"""
    try:
        work = WorkshopWork.query.get_or_404(work_id)
        
        if not _is_collab_work(work):
            return jsonify(success=False, msg='仅协作作品有历史'), 400
        
        history_list = []
        for h in work.edit_history.order_by(WorkshopWorkEditHistory.edit_time.desc()).all():
            user = h.user.username if h.user and not h.is_anonymous else '匿名'
            history_list.append({
                'id': h.id,
                'user': user,
                'edit_time': h.edit_time.isoformat() if h.edit_time else None,
                'summary': h.summary,
                'old_content': None,
                'new_content': None
            })
        
        return jsonify(success=True, history=history_list)
    except Exception as e:
        current_app.logger.error(f"历史查询失败: {str(e)}")
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    """仪表盘API"""
    try:
        from sqlalchemy import func
        
        total_works = WorkshopWork.query.count()
        
        # 使用子查询提高性能
        user_count = db.session.query(
            func.count(func.distinct(WorkshopWork.user_id))
        ).scalar() or 0
        
        return jsonify({
            'success': True, 
            'total_works': total_works, 
            'user_count': user_count,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"仪表盘数据获取失败: {str(e)}")
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/api/works', methods=['GET'])
def api_works():
    """作品列表API"""
    try:
        # 分页参数
        page, per_page = _get_pagination_params()
        query = WorkshopWork.query
        # 主题筛选
        theme = request.args.get('theme')
        if theme:
            query = query.filter(WorkshopWork.theme == theme)
        # 协作类型筛选
        is_collab = request.args.get('is_collab')
        if is_collab in ('1', '0'):
            query = query.filter(WorkshopWork.is_collab == (is_collab == '1'))
        # 关键词搜索
        keyword = request.args.get('keyword')
        if keyword and keyword.strip():
            like_expr = f"%{keyword.strip()}%"
            query = query.filter(
                (WorkshopWork.title.ilike(like_expr)) |
                (WorkshopWork.description.ilike(like_expr)) |
                (WorkshopWork.keywords.ilike(like_expr))
            )
        # 排序
        sort = request.args.get('sort', 'latest')
        if sort == 'hot':
            query = query.order_by(WorkshopWork.views.desc())
        elif sort == 'likes':
            query = query.order_by(WorkshopWork.likes.desc())
        else:
            query = query.order_by(WorkshopWork.created_at.desc())
        # 分页查询
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        # 构建响应数据
        works = []
        for w in pagination.items:
            works.append({
                'id': w.id,
                'title': w.title,
                'author': w.user.username if hasattr(w, 'user') and w.user else '',
                'description': w.description[:200] if w.description else '',  # 限制描述长度
                'theme': w.theme,
                'created_at': w.created_at.isoformat() if w.created_at else None,
                'updated_at': w.updated_at.isoformat() if w.updated_at else None,
                'views': w.views,
                'likes': w.likes,
                'is_collab': w.is_collab,
                'keywords': w.keywords,
            })
        response_data = {
            'success': True,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
            'works': works,
            'timestamp': datetime.utcnow().isoformat()
        }
        resp_json = json.dumps(response_data, ensure_ascii=False, default=str)
        # 设置缓存（可选，需有redis_client和cache_key）
        redis_client = _get_redis_client()
        cache_key = _build_cache_key()
        if redis_client:
            try:
                redis_client.setex(cache_key, 10, resp_json)  # 10秒缓存
            except Exception as e:
                current_app.logger.warning(f"Redis缓存设置失败: {str(e)}")
        return Response(resp_json, mimetype='application/json')
    except Exception as e:
        current_app.logger.error(f"作品列表查询失败: {str(e)}")
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/work/<int:work_id>')
def work_detail(work_id: int):
    """作品详情页"""
    try:
        from web.utils.render_utils import render_content
        work = WorkshopWork.query.get_or_404(work_id)
        # 增加浏览次数
        if hasattr(work, 'views'):
            work.views = (work.views or 0) + 1
            db.session.commit()
        # 判断内容类型，若以markdown为主（可后续扩展work.mode字段），此处默认markdown
        content_html = render_content(work.content, 'markdown')
        # 生成目录（简单基于markdown标题，后续可扩展更复杂目录生成）
        import re
        toc = []
        for match in re.finditer(r'<h([1-6])>(.*?)</h\1>', content_html):
            level = int(match.group(1))
            text = match.group(2)
            anchor = re.sub(r'[^\w\u4e00-\u9fa5]+', '-', text).strip('-').lower()
            toc.append({'level': level, 'text': text, 'anchor': anchor})
        # 为标题加锚点
        def add_anchors(html):
            def repl(m):
                level, text = m.group(1), m.group(2)
                anchor = re.sub(r'[^\w\u4e00-\u9fa5]+', '-', text).strip('-').lower()
                return f'<h{level} id="{anchor}">{text}</h{level}>'
            return re.sub(r'<h([1-6])>(.*?)</h\1>', repl, html)
        content_html = add_anchors(content_html)
        return render_template('workshop/work_detail.html', work=work, content_html=content_html, toc=toc)
    except Exception as e:
        current_app.logger.error(f"作品详情页加载失败: {str(e)}")
        abort(500)


@workshop_bp.route('/publish', methods=['POST'])
@login_required
def publish():
    """发布作品接口"""
    try:
        data = request.get_json(silent=True) or {}
        
        draft_id = data.get('draft_id')
        if not draft_id:
            return jsonify(success=False, msg='草稿ID不能为空'), 400
        
        pub_type = data.get('pub_type')
        pub_theme = data.get('pub_theme')
        custom_theme = data.get('custom_theme')
        
        # 1. 获取草稿
        draft = WorkshopDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()
        if not draft:
            return jsonify(success=False, msg='草稿不存在或无权访问'), 404
        
        # 防重复提交
        if hasattr(draft, 'status') and getattr(draft, 'status', None) == 'published':
            return jsonify(success=False, msg='该草稿已发布，无需重复提交'), 409
        
        # 2. 内容审核
        is_valid, error_msg, stats = _validate_json_content(draft.content or '')
        if not is_valid:
            return jsonify(success=False, msg=error_msg), 400
        
        # 3. 提取关键词
        top_words = stats.get('top_words', [])
        if isinstance(top_words, str):
            try:
                top_words = json.loads(top_words)
            except (json.JSONDecodeError, TypeError):
                top_words = []
        
        keywords_list = []
        for w in top_words[:5]:
            if isinstance(w, dict) and 'word' in w and w['word']:
                keywords_list.append(str(w['word']).strip())
        
        keywords = ','.join(keywords_list) if keywords_list else ''
        
        # 4. 确定主题
        theme = custom_theme if pub_theme == 'custom' and custom_theme else pub_theme
        if not theme:
            theme = '未分类'
        
        # 5. 创建作品
        is_collab = (pub_type == 'collab')
        work = WorkshopWork(
            user_id=current_user.id,
            title=draft.title[:200] if draft.title else '无标题',  # 限制标题长度
            description=draft.description[:500] if draft.description else '',  # 限制描述长度
            content=draft.content,
            pub_type=pub_type,
            theme=theme,
            keywords=keywords,
            is_collab=is_collab,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(work)
        
        # 标记草稿已发布
        if hasattr(draft, 'status'):
            draft.status = 'published'
            draft.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'msg': '发布成功', 
            'work_id': work.id,
            'work_title': work.title
        })
    except Exception as e:
        current_app.logger.error(f"发布作品失败: {str(e)}")
        db.session.rollback()
        return jsonify(success=False, msg='服务器内部错误'), 500


@workshop_bp.route('/docs/publish_protocol')
def publish_protocol():
    """协议文档页"""
    return render_template('workshop/publish_protocol.html')


@workshop_bp.route('/coeditor/<int:work_id>')
@login_required
def coeditor(work_id: int):
    """协作编辑页"""
    try:
        work = WorkshopWork.query.get_or_404(work_id)
        
        if not _is_collab_work(work):
            flash('仅协作作品可协作编辑', 'danger')
            return redirect(url_for('workshop.work_detail', work_id=work_id))
        
        return render_template('workshop/coeditor.html', work=work)
    except Exception as e:
        current_app.logger.error(f"协作编辑页加载失败: {str(e)}")
        abort(500)




# 作品详情与保存API
@workshop_bp.route('/api/work/<int:work_id>', methods=['GET', 'POST'])
@login_required
def api_work_detail(work_id):
    from web.models import WorkshopWork
    work = WorkshopWork.query.filter_by(id=work_id, user_id=current_user.id).first()
    if not work:
        return jsonify({'success': False, 'msg': '作品不存在'}), 404
    if request.method == 'GET':
        data = {
            'id': work.id,
            'title': work.title,
            'description': work.description,
            'content': work.content,
            'updated_at': work.updated_at.strftime('%Y-%m-%d %H:%M') if work.updated_at else None,
            'pub_type': work.pub_type,
            'is_collab': work.is_collab,
            'views': work.views,
            'likes': work.likes
        }
        return jsonify({'success': True, 'data': data})
    # POST: 保存作品，改为异步任务
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    content = (data.get('content') or '').strip()
    pub_type = (data.get('pub_type') or 'personal').strip()
    if not title or not content:
        return jsonify({'success': False, 'msg': '标题和正文不能为空'})
    # 复用 celery 异步任务保存作品内容，pub_type 作为 draft_type 传递
    from web.tasks import save_draft_task
    task = save_draft_task.apply_async(args=[current_user.id, title, content, description, pub_type])
    # 立即更新作品表基本信息（不含内容，内容由 celery 任务写入）
    work.title = title
    work.description = description
    work.pub_type = pub_type
    from web.extensions import db
    db.session.commit()
    return jsonify({'success': True, 'msg': '保存中', 'data': {'task_id': task.id, 'work_id': work.id}})
# 作品编辑页面路由
@workshop_bp.route('/re_editor/<int:work_id>', methods=['GET'])
@login_required
def work_edit(work_id):
    return render_template('workshop/work_edit.html', work_id=work_id)
# 我的作品页面路由
@workshop_bp.route('/my_works', methods=['GET'])
@login_required
def my_works_page():
    return render_template('workshop/my_works.html')
# 我的作品API：返回当前用户所有作品列表，支持分页
@workshop_bp.route('/api/my_works', methods=['GET'])
@login_required
def my_works():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    query = WorkshopWork.query.filter_by(user_id=current_user.id).order_by(WorkshopWork.updated_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    works = [
        {
            'id': w.id,
            'title': w.title,
            'description': w.description,
            'updated_at': w.updated_at.strftime('%Y-%m-%d %H:%M') if w.updated_at else None,
            'pub_type': w.pub_type,
            'is_collab': w.is_collab,
            'views': w.views,
            'likes': w.likes
        }
        for w in pagination.items
    ]
    return jsonify({
        'success': True,
        'msg': '作品列表获取成功',
        'data': {
            'works': works,
            'total': pagination.total,
            'page': page,
            'per_page': per_page
        }
    })

# 静态页面路由
@workshop_bp.route('/')
def home():
    """工坊主页"""
    return render_template('workshop/home.html')


@workshop_bp.route('/about')
def about():
    """工坊-关于页"""
    return render_template('workshop/about.html')


@workshop_bp.route('/discover')
def discover():
    """工坊-发现页"""
    return render_template('workshop/discover.html')


@workshop_bp.route('/create')
def create():
    """工坊-创作页"""
    return render_template('workshop/editor.html')
