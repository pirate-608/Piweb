import threading
import queue
import time
import uuid
from datetime import datetime

class GradingQueue:
    def __init__(self, app, data_manager, lib_instance, num_workers=1):
        self.app = app
        self.queue = queue.Queue()
        self.tasks = {}  # task_id -> {status, position, result, ...}
        self.data_manager = data_manager
        self.lib = lib_instance
        self.workers = []
        
        # Start multiple worker threads
        for i in range(num_workers):
            t = threading.Thread(target=self._worker, args=(i,), daemon=True)
            t.start()
            self.workers.append(t)
            print(f"[Queue] Started worker thread #{i+1}")

    def add_task(self, user_id, exam_data):
        # Auto Cleanup: Prevent memory leak by removing old tasks
        # If queue history exceeds 2000 items, remove the oldest 500
        if len(self.tasks) > 2000:
            try:
                # Python 3.7+ preserves insertion order, so keys() are roughly chronological
                old_keys = list(self.tasks.keys())[:500]
                for k in old_keys:
                    self.tasks.pop(k, None)
                print(f"[Queue] Auto-cleaned {len(old_keys)} old tasks from memory.")
            except Exception as e:
                print(f"[Queue] Cleanup warning: {e}")

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

    def get_status(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        # Calculate position if waiting
        if task['status'] == 'waiting':
            # This is O(N) but queue shouldn't be huge. 
            # For better performance, we could track position differently.
            # But for this scale, list(queue.queue) is fine.
            try:
                # queue.queue is a deque
                q_list = list(self.queue.queue)
                if task_id in q_list:
                    return {
                        'status': 'waiting',
                        'position': q_list.index(task_id) + 1,
                        'total_waiting': len(q_list)
                    }
            except:
                pass
        
        return {
            'status': task['status'],
            'result': task.get('result'),
            'error': task.get('error')
        }

    def get_queue_stats(self):
        return {
            'waiting_count': self.queue.qsize(),
            'active_tasks': len([t for t in self.tasks.values() if t['status'] == 'processing']),
            'total_workers': len(self.workers)
        }

    def _worker(self, worker_id):
        while True:
            task_id = self.queue.get()
            if task_id is None:
                break
            
            task = self.tasks.get(task_id)
            if not task:
                self.queue.task_done()
                continue

            # Update status
            task['status'] = 'processing'
            
            try:
                # Use app context for DB operations
                with self.app.app_context():
                    # Perform grading
                    result = self._grade_exam(task['data'])
                    
                    # Save result
                    # We need to save it to DB so the user can view it later
                    # But we also return it here for immediate display
                    
                    # Save to DB via data_manager
                    # Note: We need to reconstruct the 'exam_record' format expected by save_exam_result
                    exam_record = {
                        'id': task_id, # Use task_id as exam_id
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_score': result['total_score'],
                        'max_score': result['max_score'],
                        'details': result['details']
                    }
                    self.data_manager.save_exam_result(exam_record, user_id=task['user_id'])
                
                # Update task
                task['result'] = result
                task['status'] = 'done'
                
            except Exception as e:
                print(f"Error grading task {task_id}: {e}")
                task['status'] = 'error'
                task['error'] = str(e)
            finally:
                self.queue.task_done()

    def _grade_exam(self, data):
        # data contains: ids, user_answers (dict), all_questions (list of dicts)
        ids = data['ids']
        user_answers_map = data['user_answers'] # index -> answer string
        all_questions = data['all_questions']
        
        total_score = 0
        results = []
        exam_questions = []

        for i, q_id in enumerate(ids):
            q = next((item for item in all_questions if item['id'] == q_id), None)
            if not q: continue
            
            exam_questions.append(q)
            user_ans = user_answers_map.get(str(i), '')
            
            # Grading logic (copied from app.py)
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
