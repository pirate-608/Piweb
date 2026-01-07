import ctypes
from datetime import datetime
from config import Config
from models import db
from utils.data_manager import DataManager
from celery import shared_task
from flask_socketio import SocketIO

# Load C Library globally for the worker process
try:
    if Config.system_name == 'Windows':
        pass
        
    lib = ctypes.CDLL(Config.DLL_PATH)
    lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    lib.calculate_score.restype = ctypes.c_int
    print(f"[Celery] Successfully loaded DLL from {Config.DLL_PATH}")
except Exception as e:
    print(f"[Celery] Error loading DLL: {e}")
    lib = None

# Standalone SocketIO Client for the Worker to emit events
# Note: config.py must have CELERY_BROKER_URL defined properly
# We use the same message queue as the server
try:
    socket_emitter = SocketIO(message_queue=Config.CELERY_BROKER_URL)
except Exception as e:
    print(f"[Celery] Warning: SocketIO emitter init failed: {e}")
    socket_emitter = None

@shared_task(bind=True)
def grade_exam_task(self, user_id, data):
    """
    Celery task to grade exam.
    data: { 'ids': [], 'user_answers': {}, 'all_questions': [] }
    """
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
    exam_record = {
        'id': self.request.id, # Use Celery Task ID as Exam ID
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_score': total_score,
        'max_score': max_score,
        'details': results
    }
    
    # Save exam result and update stats
    # Note: data_manager methods might use db.session, so they are covered by 'ContextTask' in celery_utils
    data_manager.save_exam_result(exam_record, user_id=user_id)
    data_manager.update_user_stats(user_id, results)
    
    # Notify completion
    if socket_emitter:
        try:
            # Note: We send result_url so frontend can redirect
            socket_emitter.emit('status', {'status': 'done', 'percent': 100, 'result_url': f'/history/view/{task_id}'}, room=task_id)
        except Exception as e:
            print(f"Socket emit error: {e}")

    return final_result
