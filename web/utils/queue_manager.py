import threading
import queue
import time
import uuid
from datetime import datetime
from web.tasks import grade_exam_task

class GradingQueue:
    def __init__(self, app, data_manager, lib_instance, num_workers=1):
        self.app = app
        self.data_manager = data_manager
        
        # 添加线程安全锁和清理参数
        self.tasks_lock = threading.Lock()
        self.max_tasks = 2000
        self.cleanup_threshold = 500
        self.metrics = {
            'tasks_processed': 0,
            'tasks_failed': 0,
            'avg_processing_time': 0,
            'last_cleanup': time.time()
        }
        
        # 改进的Celery检测逻辑
        celery_detected = False
        try:
            celery_ext = getattr(self.app, 'extensions', {}).get('celery', None)
            if celery_ext:
                # 方式1：尝试ping所有worker
                inspector = celery_ext.control.inspect()
                ping_result = None
                
                try:
                    # 设置超时避免长时间等待
                    ping_result = inspector.ping(timeout=2)
                except Exception as ping_error:
                    print(f"[Queue] Celery ping failed: {ping_error}")
                    # 方式2：检查注册的任务
                    try:
                        registered = inspector.registered(timeout=2)
                        if registered and isinstance(registered, dict) and len(registered) > 0:
                            celery_detected = True
                            print(f"[Queue] Celery detected via registered: {list(registered.keys())}")
                    except Exception as reg_error:
                        print(f"[Queue] Celery registered check failed: {reg_error}")
                
                if ping_result and isinstance(ping_result, dict) and len(ping_result) > 0:
                    celery_detected = True
                    print(f"[Queue] Celery detected via ping with {len(ping_result)} workers")
                    
        except Exception as e:
            print(f"[Queue] Celery detection failed: {e}")
        
        # 决定运行模式
        if celery_detected:
            try:
                from web.tasks import grade_exam_task
                self.celery_task = grade_exam_task
                self.mode = 'celery'
                print("[Queue] Initialized in Distributed Mode (Celery)")
            except Exception as e:
                print(f"[Queue] Celery task import failed: {e}, falling back to Thread Mode")
                self.mode = 'thread'
        else:
            print("[Queue] Celery not detected, falling back to Thread Mode")
            self.mode = 'thread'
        
        # 线程模式初始化
        if self.mode == 'thread':
            self.queue = queue.Queue()
            self.tasks = {}
            self.lib = lib_instance
            self.workers = []
            
            # 启动清理线程
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
            
            # 启动工作线程
            for i in range(num_workers):
                t = threading.Thread(target=self._worker, args=(i,), daemon=True)
                t.start()
                self.workers.append(t)

    def add_task(self, user_id, exam_data):
        if self.mode == 'celery':
            # Celery异步分发
            result = self.celery_task.delay(user_id, exam_data)
            return result.id
        else:
            # 线程模式
            return self._add_thread_task(user_id, exam_data)

    def get_status(self, task_id):
        if self.mode == 'celery':
            try:
                from celery.result import AsyncResult
                res = AsyncResult(task_id, app=self.app.extensions['celery'])
                
                # 映射状态
                status_map = {
                    'PENDING': 'waiting',
                    'STARTED': 'processing',
                    'SUCCESS': 'done',
                    'FAILURE': 'error',
                    'RETRY': 'processing',
                    'REVOKED': 'error'
                }
                
                # 安全提取结果
                result_data = None
                if res.state == 'SUCCESS' and res.result:
                    if isinstance(res.result, dict):
                        # 只返回必要的字段，过滤敏感信息
                        result_data = {
                            'total_score': res.result.get('total_score', 0),
                            'max_score': res.result.get('max_score', 0),
                            'details': self._sanitize_details(res.result.get('details', []))
                        }
                
                return {
                    'status': status_map.get(res.state, 'waiting'),
                    'result': result_data,
                    'error': str(res.info) if res.state == 'FAILURE' else None
                }
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        else:
            return self._get_thread_status(task_id)

    def get_queue_stats(self):
        if self.mode == 'celery':
            try:
                inspector = self.app.extensions['celery'].control.inspect()
                
                # 获取活跃和等待的任务
                active_tasks = {}
                reserved_tasks = {}
                
                try:
                    active_tasks = inspector.active(timeout=2) or {}
                except Exception as e:
                    print(f"[QueueStats] Failed to get active tasks: {e}")
                
                try:
                    reserved_tasks = inspector.reserved(timeout=2) or {}
                except Exception as e:
                    print(f"[QueueStats] Failed to get reserved tasks: {e}")
                
                # 计算统计
                active_count = 0
                reserved_count = 0
                worker_count = 0
                
                if active_tasks and isinstance(active_tasks, dict):
                    active_count = sum(len(v) for v in active_tasks.values())
                    worker_count = len(active_tasks)
                
                if reserved_tasks and isinstance(reserved_tasks, dict):
                    reserved_count = sum(len(v) for v in reserved_tasks.values())
                
                # 防止异常值
                if active_count > 1000:
                    print(f"[QueueStats] active_count异常，强制归零")
                    active_count = 0
                if reserved_count > 1000:
                    print(f"[QueueStats] reserved_count异常，强制归零")
                    reserved_count = 0
                
                return {
                    'mode': 'Distributed (Celery)',
                    'active': active_count,
                    'waiting': reserved_count,
                    'workers': worker_count,
                    'last_update': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"[QueueStats] inspect异常: {e}")
                return {
                    'mode': 'Distributed (Celery)',
                    'active': 0,
                    'waiting': 0,
                    'workers': 0,
                    'error': str(e),
                    'last_update': datetime.now().isoformat()
                }
        else:
            with self.tasks_lock:
                active_count = sum(1 for t in self.tasks.values() if t.get('status') == 'processing')
                
                return {
                    'mode': 'Local Thread',
                    'active': active_count,
                    'waiting': self.queue.qsize(),
                    'total_tasks': len(self.tasks),
                    'workers': len(self.workers),
                    **self.metrics,
                    'last_update': datetime.now().isoformat()
                }

    def get_metrics(self):
        """获取性能指标"""
        with self.tasks_lock:
            return {
                **self.metrics,
                'queue_size': self.queue.qsize() if self.mode == 'thread' else 0,
                'active_tasks': sum(1 for t in self.tasks.values() if t.get('status') == 'processing'),
                'waiting_tasks': sum(1 for t in self.tasks.values() if t.get('status') == 'waiting'),
                'mode': self.mode,
                'last_cleanup': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.metrics['last_cleanup']))
            }

    # --- 线程模式实现 ---
    
    def _add_thread_task(self, user_id, exam_data):
        """添加线程任务（线程安全）"""
        # 线程安全的清理
        with self.tasks_lock:
            # 定期清理旧任务
            current_time = time.time()
            if current_time - self.metrics['last_cleanup'] > 3600:  # 每小时清理一次
                self._cleanup_old_tasks()
                self.metrics['last_cleanup'] = current_time
            
            # 防止内存溢出
            if len(self.tasks) > self.max_tasks:
                self._emergency_cleanup()
            
            # 创建新任务
            task_id = str(uuid.uuid4())
            self.tasks[task_id] = {
                'task_id': task_id,
                'user_id': user_id,
                'status': 'waiting',
                'submitted_at': datetime.now(),
                'created_at': current_time,
                'data': exam_data,
                'result': None,
                'error': None,
                'processing_time': None
            }
        
        self.queue.put(task_id)
        print(f"[Queue] Task {task_id} added to queue, total tasks: {len(self.tasks)}")
        return task_id

    def _get_thread_status(self, task_id):
        """获取线程任务状态（线程安全）"""
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            if not task:
                return {'status': 'not_found', 'error': 'Task not found'}
            
            response = {
                'status': task['status'],
                'result': task.get('result'),
                'error': task.get('error'),
                'submitted_at': task['submitted_at'].isoformat() if task.get('submitted_at') else None
            }
            
            if task.get('processing_time'):
                response['processing_time'] = task['processing_time']
            
            return response

    def _cleanup_worker(self):
        """后台清理线程"""
        while True:
            time.sleep(300)  # 每5分钟检查一次
            with self.tasks_lock:
                self._cleanup_old_tasks()

    def _cleanup_old_tasks(self):
        """清理旧任务"""
        now = time.time()
        to_delete = []
        
        for task_id, task in self.tasks.items():
            task_age = now - task.get('created_at', now)
            
            # 清理条件：
            # 1. 已完成超过1小时
            # 2. 失败超过24小时
            # 3. 总任务数超过阈值时的最早任务
            if task['status'] == 'done' and task_age > 3600:  # 1小时
                to_delete.append(task_id)
            elif task['status'] == 'error' and task_age > 86400:  # 24小时
                to_delete.append(task_id)
            elif len(self.tasks) > self.max_tasks and len(to_delete) < self.cleanup_threshold:
                to_delete.append(task_id)
        
        # 删除任务
        deleted_count = 0
        for task_id in to_delete[:self.cleanup_threshold]:
            if task_id in self.tasks:
                del self.tasks[task_id]
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"[Queue] Cleaned up {deleted_count} old tasks")
            self.metrics['last_cleanup'] = now

    def _emergency_cleanup(self):
        """紧急清理：当任务数超过最大限制时"""
        print(f"[Queue] Emergency cleanup triggered: {len(self.tasks)} > {self.max_tasks}")
        
        # 按创建时间排序，删除最早的任务
        sorted_tasks = sorted(self.tasks.items(), key=lambda x: x[1].get('created_at', 0))
        to_delete = [task_id for task_id, _ in sorted_tasks[:self.cleanup_threshold]]
        
        for task_id in to_delete:
            if task_id in self.tasks:
                del self.tasks[task_id]
        
        print(f"[Queue] Emergency cleanup removed {len(to_delete)} tasks")

    def _worker(self, worker_id):
        """工作线程"""
        while True:
            try:
                task_id = self.queue.get()
                if task_id is None:
                    break
                
                start_time = time.time()
                task = None
                
                try:
                    # 获取任务
                    with self.tasks_lock:
                        task = self.tasks.get(task_id)
                        if not task:
                            self.queue.task_done()
                            continue
                        
                        # 更新状态
                        task['status'] = 'processing'
                        task['started_at'] = datetime.now()
                    
                    print(f"[Worker-{worker_id}] Processing task {task_id}")
                    
                    # 评分处理（带超时保护）
                    result = self._grade_exam_with_timeout(task['data'], timeout=30)
                    
                    # 保存结果
                    with self.app.app_context():
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
                    
                    # 更新任务状态
                    with self.tasks_lock:
                        task['result'] = result
                        task['status'] = 'done'
                        task['processing_time'] = time.time() - start_time
                    
                    self.metrics['tasks_processed'] += 1
                    print(f"[Worker-{worker_id}] Task {task_id} completed in {task['processing_time']:.2f}s")
                    
                except TimeoutError:
                    with self.tasks_lock:
                        if task:
                            task['status'] = 'timeout'
                            task['error'] = 'Processing timeout after 30 seconds'
                    self.metrics['tasks_failed'] += 1
                    print(f"[Worker-{worker_id}] Task {task_id} timeout")
                    
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    
                    with self.tasks_lock:
                        if task:
                            task['status'] = 'error'
                            task['error'] = str(e)
                            task['traceback'] = error_trace
                    
                    self.metrics['tasks_failed'] += 1
                    print(f"[Worker-{worker_id}] Task {task_id} failed: {e}")
                    
                finally:
                    # 更新平均处理时间
                    if task and task.get('processing_time'):
                        current_avg = self.metrics['avg_processing_time']
                        total_processed = self.metrics['tasks_processed']
                        self.metrics['avg_processing_time'] = (
                            (current_avg * (total_processed - 1) + task['processing_time']) / total_processed
                            if total_processed > 0 else task['processing_time']
                        )
                    
                    self.queue.task_done()
                    
            except Exception as e:
                print(f"[Worker-{worker_id}] Critical error: {e}")
                time.sleep(1)  # 避免错误循环

    def _grade_exam_with_timeout(self, data, timeout=30):
        """带超时的评分函数"""
        import threading
        
        result_container = {}
        exception_container = {}
        
        def grade_wrapper():
            try:
                result_container['result'] = self._grade_exam(data)
            except Exception as e:
                exception_container['exception'] = e
        
        thread = threading.Thread(target=grade_wrapper)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Grading timeout after {timeout} seconds")
        
        if 'exception' in exception_container:
            raise exception_container['exception']
        
        return result_container['result']

    def _grade_exam(self, data):
        """评分逻辑（保持不变）"""
        ids = data['ids']
        user_answers_map = data['user_answers']
        all_questions = data['all_questions']
        
        total_score = 0
        results = []
        exam_questions = []

        for i, q_id in enumerate(ids):
            q = next((item for item in all_questions if item['id'] == q_id), None)
            if not q:
                continue
            
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
                    # 使用安全的编码函数
                    b_user = self._safe_encode(user_ans)
                    b_correct = self._safe_encode(correct_ans)
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

    def _safe_encode(self, text):
        """安全编码函数"""
        if not isinstance(text, str):
            text = str(text)
        
        encodings = ['gbk', 'gb2312', 'utf-8', 'latin-1']
        for encoding in encodings:
            try:
                return text.encode(encoding, errors='ignore')
            except (UnicodeEncodeError, LookupError):
                continue
        
        # 最终回退
        return text.encode('utf-8', errors='ignore')

    def _sanitize_details(self, details):
        """清理评分详情中的敏感信息"""
        if not isinstance(details, list):
            return []
        
        sanitized = []
        for detail in details:
            if isinstance(detail, dict):
                sanitized.append({
                    'id': detail.get('id'),
                    'category': detail.get('category'),
                    'score': detail.get('score'),
                    'full_score': detail.get('full_score')
                    # 不返回question、answer等敏感内容
                })
            else:
                sanitized.append(detail)
        
        return sanitized

    def shutdown(self):
        """优雅关闭"""
        print("[Queue] Shutting down...")
        
        if self.mode == 'thread':
            # 停止所有工作线程
            for _ in range(len(self.workers)):
                self.queue.put(None)
            
            # 等待线程结束
            for worker in self.workers:
                if worker.is_alive():
                    worker.join(timeout=5)
            
            print(f"[Queue] Shutdown complete. Final task count: {len(self.tasks)}")

