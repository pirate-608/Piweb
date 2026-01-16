from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask import redirect, url_for, request
from flask_login import current_user
from web.extensions import db
from web.models import User

class AdminUserView(ModelView):
    column_list = ('id', 'username', 'email', 'is_admin', 'is_banned', 'is_muted', 'stardust')
    form_columns = ('username', 'email', 'is_admin', 'is_banned', 'is_muted', 'stardust', 'password_hash')
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 50

    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login', next=request.url))

def init_admin(app):
    admin = Admin(app, name='NWW管理后台', url='/adminx')
    admin.add_view(AdminUserView(User, db.session, name='用户管理'))
    return admin
