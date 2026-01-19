import eventlet
eventlet.monkey_patch()
from web.extensions import socketio
from web.extensions import db, cache_redis
from web.models import WorkshopDraft
from flask_login import current_user
from flask import current_app

# 保存草稿Celery任务
from celery import shared_task
@shared_task(bind=True)
def save_draft_task(self, user_id, title, content, description, draft_type, work_id=None):
    task_id = self.request.id
    # 推送开始
    room_name = task_id
    try:
        socketio.emit('draft_status', {'status': 'processing', 'percent': 10, 'task_id': task_id}, room=room_name)  # 房间推送
    except Exception as e:
        print(f"[Celery] SocketIO emit failed: {e}")
    # 保存/更新草稿
    try:
        query = WorkshopDraft.query.filter_by(user_id=user_id)
        if work_id:
            query = query.filter_by(work_id=work_id)
        else:
            query = query.filter_by(title=title)
        draft = query.first()
        from datetime import datetime
        if draft:
            draft.content = content
            draft.description = description
            draft.type = draft_type
            if work_id:
                draft.work_id = work_id
            draft.updated_at = datetime.utcnow()
        else:
            draft = WorkshopDraft(
                user_id=user_id,
                work_id=work_id,
                title=title,
                description=description,
                content=content,
                type=draft_type,
                updated_at=datetime.utcnow()
            )
            db.session.add(draft)
        db.session.commit()
        # 写入Redis缓存
        if cache_redis:
            cache_redis.setex(f"draft:{user_id}:{title}", 300, draft.content)

        # 保存后自动分析内容，推送统计数据
        stats = None
        try:
            from web.services.analyzer import AnalyzerService
            from web.config import Config
            analyzer = AnalyzerService(Config.LIBANALYZER_PATH)
            stats = analyzer.analyze(content)
        except Exception as e:
            print(f"[Celery] AnalyzerService failed: {e}")
            stats = None

        # 推送完成，带上最新统计（无论成功与否 stats 字段都存在）
        try:
            msg = '草稿已保存' if stats and stats.get('ok') else (stats.get('msg') if stats and stats.get('msg') else '分析失败')
            socketio.emit('draft_status', {
                'status': 'done',
                'percent': 100,
                'task_id': task_id,
                'id': draft.id,
                'msg': msg,
                'stats': stats or {'ok': False, 'msg': 'Analyzer未返回结果'}
            }, room=room_name)  # 房间推送
        except Exception as e:
            print(f"[Celery] SocketIO emit failed: {e}")
        return {'success': True, 'id': draft.id, 'msg': msg, 'stats': stats or {'ok': False, 'msg': 'Analyzer未返回结果'}}
    except Exception as e:
        db.session.rollback()
        try:
            socketio.emit('draft_status', {'status': 'error', 'percent': 100, 'task_id': task_id, 'msg': str(e)}, room=room_name)  # 房间推送
        except Exception as e2:
            print(f"[Celery] SocketIO emit failed: {e2}")
        return {'success': False, 'msg': str(e)}
import ctypes
from datetime import datetime
from celery import shared_task

# 延迟导入配置和依赖，防止循环依赖
def get_config():
    from config import Config
    return Config

def get_socket_emitter():
    from flask_socketio import SocketIO
    Config = get_config()
    try:
        return SocketIO(
            async_mode='eventlet',
            cors_allowed_origins='*',
            message_queue=f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/0"
        )
    except Exception as e:
        print(f"[Celery] Warning: SocketIO emitter init failed: {e}")
        return None

def get_lib():
    Config = get_config()
    try:
        if Config.system_name == 'Windows':
            return None
        lib = ctypes.CDLL(Config.DLL_PATH)
        lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        lib.calculate_score.restype = ctypes.c_int
        print(f"[Celery] Successfully loaded DLL from {Config.DLL_PATH}")
        return lib
    except Exception as e:
        print(f"[Celery] Error loading DLL: {e}")
        return None

@shared_task(bind=True)
def grade_exam_task(self, user_id, data):
    """
    Celery task to grade exam.
    data: { 'ids': [], 'user_answers': {}, 'all_questions': [] }
    """
    Config = get_config()
    lib = get_lib()
    socket_emitter = get_socket_emitter()
    from utils.data_manager import DataManager
    task_id = self.request.id

    # Notify start
    if socket_emitter:
        try:
            socket_emitter.emit('status', {'status': 'processing', 'percent': 10}, room=task_id)
        except: pass

    # Initialize DataManager (lightweight)
    data_manager = DataManager(Config)

    ids = data['ids']
    user_answers_map = data['user_answers']
    all_questions = data['all_questions']

    total_score = 0
    results = []
    exam_questions = []
    total_items = len(ids)

    for i, q_id in enumerate(ids):
        q = next((item for item in all_questions if item['id'] == q_id), None)
        if not q: continue
        
        exam_questions.append(q)
        user_ans = user_answers_map.get(str(i), '')
        
        # Grading logic
        valid_answers = q['answer'].replace('；', ';').split(';')
        valid_answers = [ans.strip() for ans in valid_answers if ans.strip()]
        if not valid_answers:
            valid_answers = [q['answer']]

        score = 0
        for correct_ans in valid_answers:
            current_score = 0
            if lib:
                try:
                    # Encoding handling
                    try:
                        b_user = user_ans.encode('gbk')
                        b_correct = correct_ans.encode('gbk')
                    except:
                        b_user = user_ans.encode('utf-8')
                        b_correct = correct_ans.encode('utf-8')
                    current_score = lib.calculate_score(b_user, b_correct, q['score'])
                except Exception as e:
                    print(f"Error calling DLL: {e}")
                    # Fallback
                    current_score = q['score'] if user_ans.strip().lower() == correct_ans.strip().lower() else 0
            else:
                current_score = q['score'] if user_ans.strip().lower() == correct_ans.strip().lower() else 0
            
            if current_score > score:
                score = current_score
        
        total_score += score
        results.append({
            'id': q['id'],
            'category': q.get('category', '默认题集'),
            'question': q['content'],
            'user_ans': user_ans,
            'correct_ans': q['answer'],
            'score': score,
            'full_score': q['score']
        })
        
        # Emit progress update every 5 items or 20%
        if socket_emitter and total_items > 0 and (i % 5 == 0 or i == total_items - 1):
             percent = 10 + int((i + 1) / total_items * 80) # 10% to 90%
             try:
                 socket_emitter.emit('status', {'status': 'processing', 'percent': percent}, room=task_id)
             except: pass
        
    max_score = sum(q['score'] for q in exam_questions)
    
    final_result = {
        'total_score': total_score,
        'max_score': max_score,
        'details': results
    }

    # Save to Database
    # We need to reconstruct the 'exam_record' format expected by save_exam_result
    exam_category = data.get('category', '默认题集')
    exam_record = {
        'id': self.request.id, # Use Celery Task ID as Exam ID
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_score': total_score,
        'max_score': max_score,
        'details': results,
        'category': exam_category
    }
    # Save exam result and update stats
    data_manager.save_exam_result(exam_record, user_id=user_id, category=exam_category)
    data_manager.update_user_stats(user_id, results)
    
    # Notify completion
    if socket_emitter:
        try:
            # Note: We send result_url so frontend can redirect
            socket_emitter.emit('status', {'status': 'done', 'percent': 100, 'result_url': f'/history/view/{task_id}'}, room=task_id)
        except Exception as e:
            print(f"Socket emit error: {e}")

    return final_result
