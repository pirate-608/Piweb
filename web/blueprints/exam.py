from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response
from flask_login import login_required, current_user
from web.extensions import db
from web.models import User
import random
import io
import csv
from datetime import datetime



exam_bp = Blueprint('exam', __name__)

# ...existing code...

# 批量删除接口，移到 exam_bp 定义之后
@exam_bp.route('/history/batch_delete', methods=['POST'])
@login_required
def batch_delete_history():
    if not current_user.is_admin:
        flash('只有管理员可以批量删除记录', 'danger')
        return redirect(url_for('exam.history'))
    ids = request.form.getlist('selected_ids')
    if not ids:
        flash('未选择任何记录', 'warning')
        return redirect(url_for('exam.history'))
    deleted = 0
    data_manager = getattr(current_app, 'data_manager', None)
    for rid in ids:
        if data_manager and data_manager.delete_result(rid):
            deleted += 1
    flash(f'已批量删除 {deleted} 条记录', 'success')
    return redirect(url_for('exam.history'))

@exam_bp.route('/select_set')
@login_required
def select_set():
    data_manager = getattr(current_app, 'data_manager', None)
    questions = data_manager.load_questions() if data_manager else []
    if not questions:
        flash('题库为空，请先添加题目！', 'warning')
        return redirect(url_for('main.index'))
        
    categories = {}
    for q in questions:
        cat = q.get('category', '默认题集')
        categories[cat] = categories.get(cat, 0) + 1
        
    return render_template('select_set.html', categories=categories, total_count=len(questions))

@exam_bp.route('/start_exam')
@login_required
def start_exam():
    return redirect(url_for('exam.select_set'))

@exam_bp.route('/exam', methods=['GET', 'POST'])
@login_required
def exam():
    category = request.args.get('category')
    
    if request.method == 'GET' and not session.get('in_exam'):
        if not category:
            return redirect(url_for('exam.select_set'))
        session['in_exam'] = True
        session['start_time'] = datetime.now().timestamp()
        session['exam_category'] = category

    if not session.get('in_exam'):
        return redirect(url_for('main.index'))

    data_manager = getattr(current_app, 'data_manager', None)
    all_questions = data_manager.load_questions() if data_manager else []
    
    current_category = session.get('exam_category', 'all')
    if current_category != 'all':
        filtered_ids = [q['id'] for q in all_questions if q.get('category', '默认题集') == current_category]
    else:
        filtered_ids = [q['id'] for q in all_questions]

    if not filtered_ids:
        session.pop('in_exam', None)
        flash('该题集没有题目！', 'warning')
        return redirect(url_for('exam.select_set'))

    if request.method == 'GET':
        random.shuffle(filtered_ids)
        session['exam_ids'] = filtered_ids
        
        shuffled_questions = [q for q in all_questions if q['id'] in filtered_ids]
        shuffled_questions.sort(key=lambda x: filtered_ids.index(x['id']))
        
        start_time = session.get('start_time', datetime.now().timestamp())
        # Dynamic duration: 5 minutes per question
        duration_sec = len(filtered_ids) * 5 * 60
        elapsed = datetime.now().timestamp() - start_time
        remaining_sec = max(0, int(duration_sec - elapsed))
        
        return render_template('exam.html', questions=shuffled_questions, remaining_sec=remaining_sec)

    if request.method == 'POST':
        ids = session.get('exam_ids')
        if not ids:
             return redirect(url_for('main.index'))
             
        user_answers = {}
        for i, q_id in enumerate(ids):
             user_answers[str(i)] = request.form.get(f'q_{i}', '')
        
        exam_data = {
            'ids': ids,
            'user_answers': user_answers,
            'all_questions': all_questions,
            'category': current_category
        }
        
        # Access grading_queue via current_app.extensions if available, or just check 'grading_queue' attr
        # We will assume it's attached to current_app
        task_id = current_app.grading_queue.add_task(current_user.id, exam_data)

        session.pop('in_exam', None)
        session.pop('exam_ids', None)
        
        return redirect(url_for('exam.waiting', task_id=task_id))
    
    return redirect(url_for('main.index'))

@exam_bp.route('/waiting/<task_id>')
@login_required
def waiting(task_id):
    return render_template('waiting.html', task_id=task_id)

@exam_bp.route('/queue/status/<task_id>')
@login_required
def queue_status(task_id):
    grading_queue = current_app.grading_queue
    status = grading_queue.get_status(task_id)
    if not status:
        return {'status': 'error', 'error': 'Task not found'}, 404
    return status

@exam_bp.route('/history')
@login_required
def history():
    user_id = None if current_user.is_admin else current_user.id
    data_manager = getattr(current_app, 'data_manager', None)
    results = data_manager.load_results(user_id=user_id) if data_manager else []
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    
    q = request.args.get('q', '').strip()
    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in str(r.get('username', '')).lower() or q_lower in str(r.get('timestamp', '')).lower()]
        start_time = request.args.get('start_time', '').strip()
        end_time = request.args.get('end_time', '').strip()
        if start_time:
            results = [r for r in results if r.get('timestamp', '') >= start_time]
        if end_time:
            results = [r for r in results if r.get('timestamp', '') <= end_time]
        return render_template('history.html', results=results, search_query=q, start_time=start_time, end_time=end_time)
        
    return render_template('history.html', results=results, search_query=q)

@exam_bp.route('/history/view/<result_id>')
@login_required
def view_history(result_id):
    data_manager = getattr(current_app, 'data_manager', None)
    record = data_manager.get_result(result_id) if data_manager else None
    if not record:
        flash('记录未找到', 'error')
        return redirect(url_for('exam.history'))
        
    if not current_user.is_admin and record.get('user_id') != current_user.id:
        flash('您没有权限查看此记录', 'danger')
        return redirect(url_for('exam.history'))
        
    return render_template('result.html', total_score=record['total_score'], results=record['details'], is_history=True)

@exam_bp.route('/export_history')
@login_required
def export_history():
    user_id = None if current_user.is_admin else current_user.id
    results = data_manager.load_results(user_id=user_id)
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['用户', '时间', '得分', '满分', '得分率'])
    
    for r in results:
        score = r.get('total_score', 0)
        max_s = r.get('max_score', 0)
        percentage = f"{(score / max_s * 100):.1f}%" if max_s > 0 else "0.0%"
        username = r.get('username', 'Unknown')
        writer.writerow([username, r['timestamp'], score, max_s, percentage])
        
    output.seek(0)
    
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=exam_history.csv"}
    )

@exam_bp.route('/history/delete/<result_id>', methods=['POST'])
@login_required
def delete_history(result_id):
    record = data_manager.get_result(result_id)
    if not record:
        flash('记录未找到', 'error')
        return redirect(url_for('exam.history'))
        
    if not current_user.is_admin:
        flash('只有管理员可以删除记录', 'danger')
        return redirect(url_for('exam.history'))

    data_manager.delete_result(result_id)
    flash('记录已删除', 'success')
    return redirect(url_for('exam.history'))
