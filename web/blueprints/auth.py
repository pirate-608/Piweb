from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, data_manager
from web.models import User

auth_bp = Blueprint('auth', __name__)

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
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('auth.register'))
            
        if data_manager.create_user(username, password):
            flash('注册成功，请登录', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('用户名已存在', 'danger')
            
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
