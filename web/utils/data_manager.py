import os
import json
import shutil
from datetime import datetime, timedelta
from web.models import db, Question, ExamResult, User, UserCategoryStat, UserPermission, StardustHistory

class DataManager:
    def __init__(self, config):
        self.config = config
        self._ensure_directories()
        self._check_legacy_db()

    def _ensure_directories(self):
        if not os.path.exists(self.config.UPLOAD_FOLDER):
            os.makedirs(self.config.UPLOAD_FOLDER)
        if hasattr(self.config, 'INSTANCE_PATH') and not os.path.exists(self.config.INSTANCE_PATH):
            os.makedirs(self.config.INSTANCE_PATH)

    def _check_legacy_db(self):
        # 兼容 Celery worker 启动时无 SQLite 迁移需求
        pass

    def export_questions_to_txt(self):
        """
        导出所有题目到 questions.txt，格式：题目|答案|分值|图片文件名|类别
        """
        questions = Question.query.order_by(Question.id).all()
        lines = []
        for q in questions:
            content = q.content.replace('\n', '[NEWLINE]') if q.content else ''
            answer = q.answer if q.answer else ''
            score = str(q.score) if q.score is not None else '0'
            image = q.image if q.image else ''
            category = q.category if q.category else '默认题集'
            line = f"{content}|{answer}|{score}|{image}|{category}"
            lines.append(line)
        data_file = getattr(self.config, 'DATA_FILE', 'questions.txt')
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print(f"[DataManager] 已导出所有题目到 {data_file}")
        except Exception as e:
            print(f"[DataManager] 导出题目失败: {e}")
    def save_all_questions(self, questions):
        # This is hard to map to DB efficiently without IDs.
        # We will avoid using this in the new app.py
        pass

    def get_questions_paginated(self, page=1, per_page=10, search=None, category=None):
        query = Question.query
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Question.content.like(search_term)) | 
                (Question.category.like(search_term))
            )
        if category and category != 'all':
            query = query.filter_by(category=category)
        
        return query.order_by(Question.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_system_stats(self):
        total_questions = Question.query.count()
        total_exams = ExamResult.query.count()
        
        # Calculate average accuracy
        from sqlalchemy import func
        total_score_sum = db.session.query(func.sum(ExamResult.total_score)).scalar() or 0
        total_max_sum = db.session.query(func.sum(ExamResult.max_score)).scalar() or 0
        
        if total_max_sum > 0:
            avg_accuracy = round((total_score_sum / total_max_sum) * 100, 1)
        else:
            avg_accuracy = 0
            
        return {
            'total_questions': total_questions,
            'total_exams': total_exams,
            'avg_accuracy': avg_accuracy
        }

    def get_categories(self):
        # Use distinct query
        categories = db.session.query(Question.category).distinct().all()
        return sorted([c[0] for c in categories if c[0]])

    def load_results(self, user_id=None):
        query = ExamResult.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        results = query.order_by(ExamResult.timestamp.desc()).all()
        # 兼容旧数据: 若无 category 字段，尝试从 details 推断
        for r in results:
            if not hasattr(r, 'category') or not r.category:
                # 尝试从 details 里找
                if r.details and isinstance(r.details, list) and r.details:
                    cat = r.details[0].get('category') if isinstance(r.details[0], dict) else None
                    if cat:
                        r.category = cat
                    else:
                        r.category = '默认题集'
        return [r.to_dict() for r in results]

    def save_exam_result(self, result_dict, user_id=None, category='默认题集'):
        print(f"[DataManager] Saving exam result: {result_dict['id']} for user: {user_id}")
        # 优先 result_dict['category']，否则用参数
        cat = result_dict.get('category') or category or '默认题集'
        result = ExamResult(
            id=result_dict['id'],
            timestamp=result_dict['timestamp'],
            total_score=result_dict['total_score'],
            max_score=result_dict['max_score'],
            user_id=user_id,
            category=cat
        )
        result.details = result_dict['details']
        try:
            db.session.add(result)
            db.session.commit()
            print(f"[DataManager] Successfully saved result {result_dict['id']}")
            
            # Award Stardust
            if user_id:
                score = result_dict['total_score']
                max_s = result_dict['max_score']
                self.award_stardust(user_id, category, score, max_s)
                
        except Exception as e:
            db.session.rollback()
            print(f"[DataManager] Error saving result: {e}")
            raise e

    def award_stardust(self, user_id, category, score, max_score):
        if max_score <= 0: return
        percentage = (score / max_score) * 100
        
        # Determine reward tier
        reward = 0
        if percentage >= 90: # Excellent
            reward = 15
        elif percentage >= 80: # Good
            reward = 10
        elif percentage >= 60: # Qualified
            reward = 5
            
        if reward == 0:
            return
            
        # Check 24h limit for this category
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_entry = StardustHistory.query.filter(
            StardustHistory.user_id == user_id,
            StardustHistory.category == category,
            StardustHistory.created_at >= last_24h
        ).first()
        
        if recent_entry:
            print(f"[Stardust] User {user_id} already rewarded for {category} in last 24h")
            return
            
        # Award
        try:
            user = User.query.get(user_id)
            if user:
                user.stardust = (user.stardust or 0) + reward
                history = StardustHistory(
                    user_id=user_id,
                    category=category,
                    amount=reward,
                    reason='exam_reward'
                )
                db.session.add(history)
                db.session.commit()
                print(f"[Stardust] User {user_id} earned {reward} stardust (Cat: {category})")
        except Exception as e:
            print(f"[Stardust] Error: {e}")
            db.session.rollback()

    def get_result(self, result_id):
        r = ExamResult.query.get(result_id)
        return r.to_dict() if r else None

    def delete_result(self, result_id):
        r = ExamResult.query.get(result_id)
        if r:
            # Rollback stats
            try:
                self.rollback_user_stats(r.user_id, r.details)
            except Exception as e:
                print(f"Error rolling back stats: {e}")
            
            db.session.delete(r)
            db.session.commit()

    def rollback_user_stats(self, user_id, results):
        """
        Reverse the effect of update_user_stats.
        """
        category_results = {}
        for r in results:
            cat = r.get('category', '默认题集')
            if cat not in category_results:
                category_results[cat] = {'score': 0, 'max_score': 0}
            category_results[cat]['score'] += r.get('score', 0)
            category_results[cat]['max_score'] += r.get('full_score', 0)
        
        for cat, data in category_results.items():
            stat = UserCategoryStat.query.filter_by(user_id=user_id, category=cat).first()
            if stat:
                stat.total_attempts = max(0, (stat.total_attempts or 1) - 1)
                stat.total_score = max(0, (stat.total_score or 0) - data['score'])
                stat.total_max_score = max(0, (stat.total_max_score or 0) - data['max_score'])
        
        # We don't revoke permissions or stardust automatically as it's complex to track back exactly
        # But stats should be consistent.


    def create_user(self, username, password, is_admin=False):
        print(f"[调试] 进入 create_user: username={username}, is_admin={is_admin}")
        all_users = User.query.all()
        print(f"[调试] 当前所有用户名: {[u.username for u in all_users]}")
        if User.query.filter_by(username=username).first():
            print(f"[调试] 用户名 {username} 已存在，注册失败")
            return False
        user = User(username=username, is_admin=is_admin)
        user.set_password(password)
        print(f"[调试] 即将 add 用户: {user.username}")
        db.session.add(user)
        print(f"[调试] 已 add 用户: {user.username}，准备 commit")
        db.session.commit()
        print(f"[调试] 已 commit 用户: {user.username}")
        return True

    def get_user_dashboard_stats(self, user_id):
        # 1. Score Trend (Last 7 exams)
        recent_exams = ExamResult.query.filter_by(user_id=user_id)\
            .order_by(ExamResult.timestamp.desc())\
            .limit(7).all()
        recent_exams.reverse() # Make it chronological
        
        trend_labels = [r.timestamp.split(' ')[0] for r in recent_exams]
        trend_data = [r.total_score for r in recent_exams]
        
        # 2. Error Analysis (Top 5 wrong questions from last 20 exams)
        analyze_exams = ExamResult.query.filter_by(user_id=user_id)\
            .order_by(ExamResult.timestamp.desc())\
            .limit(20).all()
            
        question_stats = {} # {short_content: {wrong: 0, total: 0}}
        
        for exam in analyze_exams:
            details = exam.details
            if not details: continue
            for q in details:
                content = q.get('question')
                if not content: continue
                
                # Truncate content
                short_content = (content[:10] + '..') if len(content) > 10 else content
                
                if short_content not in question_stats:
                    question_stats[short_content] = {'wrong': 0, 'total': 0}
                
                question_stats[short_content]['total'] += 1
                if q.get('score', 0) < q.get('full_score', 0):
                    question_stats[short_content]['wrong'] += 1
                    
        # Calculate error counts
        error_list = []
        for content, stats in question_stats.items():
            if stats['wrong'] > 0:
                error_list.append({'label': content, 'count': stats['wrong']})
        
        # Sort by error count descending
        error_list.sort(key=lambda x: x['count'], reverse=True)
        top_errors = error_list[:5]
        
        return {
            'trend': {
                'labels': trend_labels,
                'data': trend_data
            },
            'errors': {
                'labels': [x['label'] for x in top_errors],
                'data': [x['count'] for x in top_errors]
            }
        }

    def update_user_stats(self, user_id, results):
        """
        Update user statistics based on exam results.
        results: list of dicts with keys 'category', 'score', 'full_score'
        """
        # Group results by category
        category_results = {}
        for r in results:
            cat = r.get('category', '默认题集')
            if cat not in category_results:
                category_results[cat] = {'score': 0, 'max_score': 0}
            category_results[cat]['score'] += r.get('score', 0)
            category_results[cat]['max_score'] += r.get('full_score', 0)
        
        # Update database
        for cat, data in category_results.items():
            stat = UserCategoryStat.query.filter_by(user_id=user_id, category=cat).first()
            if not stat:
                stat = UserCategoryStat(user_id=user_id, category=cat, total_attempts=0, total_score=0, total_max_score=0)
                db.session.add(stat)
            
            stat.total_attempts = (stat.total_attempts or 0) + 1
            stat.total_score = (stat.total_score or 0) + data['score']
            stat.total_max_score = (stat.total_max_score or 0) + data['max_score']
            
            # Check for permission grant (e.g., > 80% accuracy and > 5 attempts)
            # This is a simple rule, can be made more complex
            if stat.total_max_score > 0:
                accuracy = stat.total_score / stat.total_max_score
                if accuracy >= 0.8 and stat.total_attempts >= 3:
                    self.grant_permission(user_id, cat)
        
        db.session.commit()

    def grant_permission(self, user_id, category):
        perm = UserPermission.query.filter_by(user_id=user_id, category=category).first()
        if not perm:
            perm = UserPermission(user_id=user_id, category=category)
            db.session.add(perm)
            # db.session.commit() # Commit is handled by caller

    def check_permission(self, user_id, category):
        user = User.query.get(user_id)
        if user and user.is_admin:
            return True
        perm = UserPermission.query.filter_by(user_id=user_id, category=category).first()
        return perm is not None

    def get_leaderboard_data(self):
        """
        Get leaderboard data.
        Returns a dict with 'global' and 'categories' keys.
        """
        # Global Leaderboard (Average Accuracy across all categories)
        # We can aggregate UserCategoryStat
        users = User.query.all()
        global_leaderboard = []
        
        for user in users:
            stats = UserCategoryStat.query.filter_by(user_id=user.id).all()
            total_score = sum(s.total_score for s in stats)
            total_max = sum(s.total_max_score for s in stats)
            accuracy = (total_score / total_max * 100) if total_max > 0 else 0
            
            if total_max > 0: # Only include users who have taken exams
                global_leaderboard.append({
                    'user_id': user.id,
                    'username': user.username,
                    'stardust': user.stardust,
                    'level_info': user.level_info,
                    'accuracy': round(accuracy, 1),
                    'total_exams': sum(s.total_attempts for s in stats)
                })
        
        global_leaderboard.sort(key=lambda x: x['accuracy'], reverse=True)
        
        # Category Leaderboards
        categories = self.get_categories()
        category_leaderboards = {}
        
        for cat in categories:
            cat_stats = UserCategoryStat.query.filter_by(category=cat).all()
            leaderboard = []
            for stat in cat_stats:
                if stat.total_max_score > 0:
                    acc = (stat.total_score / stat.total_max_score * 100)
                    leaderboard.append({
                        'user_id': stat.user_id,
                        'username': stat.user.username,
                        'stardust': stat.user.stardust,
                        'level_info': stat.user.level_info,
                        'accuracy': round(acc, 1),
                        'attempts': stat.total_attempts
                    })
            leaderboard.sort(key=lambda x: x['accuracy'], reverse=True)
            if leaderboard:
                category_leaderboards[cat] = leaderboard
                
        return {
            'global': global_leaderboard[:10], # Top 10
            'categories': category_leaderboards
        }

    def init_db(self, app):
        with app.app_context():
            db.create_all()
            if User.query.filter_by(is_admin=True).count() == 0:
                admin = User(username='admin', is_admin=True)
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("Created default admin user (admin/admin123) because no admin existed.")

    def get_question(self, q_id):
        q = Question.query.get(q_id)
        return q.to_dict() if q else None

    def update_question(self, q_id, content, answer, score, image=None, category=None):
        q = Question.query.get(q_id)
        if q:
            q.content = content
            q.answer = answer
            q.score = score
            if image is not None:
                q.image = image
            if category is not None:
                q.category = category
            db.session.commit()
            self.export_questions_to_txt()
    
    def delete_question(self, q_id):
        q = Question.query.get(q_id)
        if not q:
            return None
        image_filename = q.image if q.image else None
        db.session.delete(q)
        db.session.commit()
        self.export_questions_to_txt()
        return image_filename

    def load_questions(self):
        questions = Question.query.order_by(Question.id).all()
        return [q.to_dict() for q in questions]

    def save_question(self, content, answer, score=10, image=None, category='默认题集'):
        """
        保存单个题目到数据库，并导出所有题目到 txt
        """
        q = Question(
            content=content,
            answer=answer,
            score=score,
            image=image,
            category=category
        )
        db.session.add(q)
        db.session.commit()
        self.export_questions_to_txt()
        return q.id

