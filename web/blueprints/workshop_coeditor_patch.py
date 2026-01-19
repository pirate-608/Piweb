@workshop_bp.route('/coeditor/<int:work_id>')
@login_required
def coeditor(work_id):
    work = WorkshopWork.query.get_or_404(work_id)
    if not work.is_collab:
        flash('仅协作作品可协作编辑', 'danger')
        return redirect(url_for('workshop.work_detail', work_id=work_id))
    return render_template('workshop/coeditor.html', work=work)

# 提供协作编辑页内容API，供前端加载原内容
@workshop_bp.route('/api/work/<int:work_id>')
@login_required
def api_work_content(work_id):
    work = WorkshopWork.query.get_or_404(work_id)
    if not work.is_collab:
        return jsonify(success=False, msg='仅协作作品可编辑'), 400
    return jsonify(success=True, work={
        'id': work.id,
        'title': work.title,
        'description': work.description,
        'content': work.content
    })
