
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from web.extensions import db
from web.models import User

auth_bp = Blueprint('auth', __name__)

# 账户注销（删除账户）功能
@auth_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    if user is None:
        flash('用户不存在', 'danger')
        return redirect(url_for('main.index'))
    # 可扩展：删除用户相关的其他数据（如帖子、评论、成绩等）
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('您的账户已被永久删除', 'info')
    return redirect(url_for('auth.register'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        login_id = request.form.get('username') 
        password = request.form.get('password')
        
        user = User.query.filter((User.username == login_id) | (User.email == login_id)).first()
        
        if user and user.check_password(password):
            if user.is_banned:
                flash('该账号已被封禁，无法登录', 'danger')
                return render_template('login.html')
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('用户名或密码错误', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        print(f"[调试] register视图收到POST: {request.form}")
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        print(f"[调试] register视图解析参数: username={username}, password={password}, confirm_password={confirm_password}")

        if password != confirm_password:
            print("[调试] 两次输入的密码不一致，注册失败")
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('auth.register'))

        data_manager = getattr(current_app, 'data_manager', None)
        print(f"[调试] data_manager: {data_manager}")
        if data_manager:
            print(f"[调试] 即将调用 create_user: username={username}, password={password}")
            result = data_manager.create_user(username, password)
            print(f"[调试] create_user 返回: {result}")
            if result:
                flash('注册成功，请登录', 'success')
                print("[调试] 注册成功，跳转登录页")
                return redirect(url_for('auth.login'))
            else:
                flash('用户名已存在', 'danger')
                print("[调试] 用户名已存在，注册失败")
        else:
            print("[调试] data_manager 不存在，无法注册")
            
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录', 'info')
    return redirect(url_for('auth.login'))
