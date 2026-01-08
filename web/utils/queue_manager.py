import threading
import queue
import time
import uuid
from datetime import datetime

class GradingQueue:
    def __init__(self, app, data_manager, lib_instance, num_workers=1):
        self.app = app
        self.data_manager = data_manager
        
        # Check if Celery is enabled/configured simply by trying to import task
        try:
            from tasks import grade_exam_task
            self.celery_task = grade_exam_task
            self.mode = 'celery'
            print("[Queue] Initialized in Distributed Mode (Celery)")
        except Exception as e:
            print(f"[Queue] Celery not detected ({e}), falling back to Thread Mode")
            self.mode = 'thread'
            self.queue = queue.Queue()
            self.tasks = {} 
            self.lib = lib_instance
            self.workers = []
            for i in range(num_workers):
                t = threading.Thread(target=self._worker, args=(i,), daemon=True)
                t.start()
                self.workers.append(t)

    def add_task(self, user_id, exam_data):
        if self.mode == 'celery':
            # Async dispatch to Redis/Celery
            result = self.celery_task.delay(user_id, exam_data)
            return result.id
        else:
            # Fallback to Thread Logic
            return self._add_thread_task(user_id, exam_data)

    def get_status(self, task_id):
        if self.mode == 'celery':
            try:
                # Retrieve async result from Celery
                from celery.result import AsyncResult
                res = AsyncResult(task_id, app=self.app.extensions['celery'])
                
                status_map = {
                    'PENDING': 'waiting',
                    'STARTED': 'processing',
                    'SUCCESS': 'done',
                    'FAILURE': 'error',
                    'RETRY': 'processing'
                }
                
                return {
                    'status': status_map.get(res.state, 'waiting'),
                    'result': res.result if res.state == 'SUCCESS' else None,
                    'error': str(res.result) if res.state == 'FAILURE' else None
                }
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        else:
            return self._get_thread_status(task_id)

    def get_queue_stats(self):
        if self.mode == 'celery':
            try:
                # Basic Celery Stats
                i = self.app.extensions['celery'].control.inspect()
                active = i.active()
                reserved = i.reserved()
                
                active_count = sum(len(v) for v in active.values()) if active else 0
                reserved_count = sum(len(v) for v in reserved.values()) if reserved else 0
                
                return {
                    'mode': 'Distributed (Celery)',
                    'active': active_count,
                    'waiting': reserved_count,
                    'workers': len(active) if active else 0
                }
            except Exception as e:
                return {'mode': 'Distributed (Celery)', 'error': str(e)}
        else:
            return {
                'mode': 'Local Thread',
                'active': len(self.workers),
                'waiting': self.queue.qsize(),
                'total_tasks': len(self.tasks)
            }

    # --- Legacy Thread Implementation ---
    def _add_thread_task(self, user_id, exam_data):
        # ... (Existing Clean up logic)
        # Auto Cleanup: Prevent memory leak by removing old tasks
        if len(self.tasks) > 2000:
             # ... existing cleanup ...
             try:
                old_keys = list(self.tasks.keys())[:500]
                for k in old_keys:
                    self.tasks.pop(k, None)
             except: pass

        task_id = str(uuid.uuid4())
        task_info = {
            'task_id': task_id,
            'user_id': user_id,
            'status': 'waiting',
            'submitted_at': datetime.now(),
            'data': exam_data,
            'result': None
        }
        self.tasks[task_id] = task_info
        self.queue.put(task_id)
        return task_id

    def _get_thread_status(self, task_id):
        task = self.tasks.get(task_id)
        if not task: return None
        return {
            'status': task['status'],
            'result': task.get('result'),
            'error': task.get('error')
        }

    # ... _worker and _grade_exam methods remain for fallback ...
    def _worker(self, worker_id):
        while True:
            task_id = self.queue.get()
            if task_id is None: break
            task = self.tasks.get(task_id)
            if not task:
                self.queue.task_done()
                continue
            task['status'] = 'processing'
            try:
                with self.app.app_context():
                    # For thread mode, we still use local _grade_exam
                    result = self._grade_exam(task['data'])
                    
                    exam_record = {
                        'id': task_id,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_score': result['total_score'],
                        'max_score': result['max_score'],
                        'details': result['details']
                    }
                    cat = task['data'].get('category', 'all')
                    self.data_manager.save_exam_result(exam_record, user_id=task['user_id'], category=cat)
                    self.data_manager.update_user_stats(task['user_id'], result['details'])
                
                task['result'] = result
                task['status'] = 'done'
            except Exception as e:
                task['status'] = 'error'; task['error'] = str(e)
            finally:
                self.queue.task_done()

    def _grade_exam(self, data):
        # ... (Same logic as before, used for Thread mode) ...
        # Copied from original file
        ids = data['ids']
        user_answers_map = data['user_answers'] 
        all_questions = data['all_questions']
        
        total_score = 0
        results = []
        exam_questions = []

        for i, q_id in enumerate(ids):
            q = next((item for item in all_questions if item['id'] == q_id), None)
            if not q: continue
            
            exam_questions.append(q)
            user_ans = user_answers_map.get(str(i), '')
            
            valid_answers = q['answer'].replace('；', ';').split(';')
            valid_answers = [ans.strip() for ans in valid_answers if ans.strip()]
            if not valid_answers:
                valid_answers = [q['answer']]

            score = 0
            for correct_ans in valid_answers:
                current_score = 0
                if self.lib:
                    try:
                        b_user = user_ans.encode('gbk')
                        b_correct = correct_ans.encode('gbk')
                    except:
                        b_user = user_ans.encode('utf-8')
                        b_correct = correct_ans.encode('utf-8')
                    current_score = self.lib.calculate_score(b_user, b_correct, q['score'])
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
            
        max_score = sum(q['score'] for q in exam_questions)
        return {
            'total_score': total_score,
            'max_score': max_score,
            'details': results
        }

