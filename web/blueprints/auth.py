
import random
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from web.extensions import db, mail
from web.models import User
from flask_mail import Message

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
        login_mode = request.form.get('login_mode', 'password')
        if login_mode == 'password':
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
        elif login_mode == 'code':
            email = request.form.get('email')
            code = request.form.get('code')
            user = User.query.filter_by(email=email).first()
            code_session = session.get('login_code')
            code_expire = session.get('login_code_expire', 0)
            if not user:
                flash('该邮箱未注册', 'danger')
            elif not code or not code_session or code != code_session or time.time() > code_expire:
                flash('验证码错误或已过期', 'danger')
            elif user.is_banned:
                flash('该账号已被封禁，无法登录', 'danger')
            else:
                login_user(user)
                session.pop('login_code', None)
                session.pop('login_code_expire', None)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.index'))
    return render_template('login.html')

# 邮箱验证码发送API
@auth_bp.route('/send_code', methods=['POST'])
def send_code():
    email = request.form.get('email')
    if not email:
        return jsonify({'success': False, 'msg': '邮箱不能为空'}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'msg': '该邮箱未注册'}), 400
    # 限制发送频率
    last_send = session.get('last_code_send', 0)
    if time.time() - last_send < 60:
        return jsonify({'success': False, 'msg': '请勿频繁获取验证码'}), 429
    code = f"{random.randint(100000, 999999)}"
    session['login_code'] = code
    session['login_code_expire'] = time.time() + 300  # 5分钟有效
    session['last_code_send'] = time.time()
    try:
        msg = Message(subject="NWW 登录验证码", recipients=[email], body=f"您的登录验证码为：{code}\n5分钟内有效。如非本人操作请忽略。")
        mail.send(msg)
    except Exception as e:
        return jsonify({'success': False, 'msg': f'邮件发送失败: {e}'}), 500
    return jsonify({'success': True, 'msg': '验证码已发送，请查收邮箱'})

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
