from web.extensions import db
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
from sqlalchemy import event
from sqlalchemy.engine import Engine

# 工坊正式作品表
class WorkshopWork(db.Model):
    __tablename__ = 'workshop_work'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    pub_type = db.Column(db.String(32))  # personal/collab
    theme = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    keywords = db.Column(db.String(256))  # 关键词，逗号分隔或JSON
    views = db.Column(db.Integer, default=0)  # 浏览量
    likes = db.Column(db.Integer, default=0)  # 点赞数
    is_collab = db.Column(db.Boolean, default=False)  # 是否协作作品
    hotness = db.Column(db.Float, default=0.0, index=True)  # 热度分数
    hotness_milestone = db.Column(db.Integer, default=0)  # 已达成的最高热度档位（如0、1、2...）
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('workshop_works', lazy=True))
    # 协作编辑锁
    edit_lock_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    edit_lock_time = db.Column(db.DateTime, nullable=True)
    edit_lock_user = db.relationship('User', foreign_keys=[edit_lock_user_id], backref='editing_works')

# 协作编辑历史表
class WorkshopWorkEditHistory(db.Model):
    __tablename__ = 'workshop_work_edit_history'
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey('workshop_work.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    edit_time = db.Column(db.DateTime, default=datetime.utcnow)
    old_content = db.Column(db.Text)
    new_content = db.Column(db.Text)
    summary = db.Column(db.String(256))
    work = db.relationship('WorkshopWork', backref=db.backref('edit_history', lazy=True, cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('edit_histories', lazy=True))

class WorkshopDraft(db.Model):
    __tablename__ = 'workshop_draft'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    work_id = db.Column(db.Integer, db.ForeignKey('workshop_work.id'), nullable=True)  # 新增，支持草稿与作品关联
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    type = db.Column(db.String(32))  # online/file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', backref='workshop_drafts')
    work = db.relationship('WorkshopWork', backref='drafts', foreign_keys=[work_id])

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    topic = db.relationship('Topic', backref=db.backref('posts', lazy=True, cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('posts', lazy=True))
    replies = db.relationship('Post', backref=db.backref('parent', remote_side=[id]), lazy=True)
    likes = db.relationship('PostLike', backref='post', lazy=True, cascade="all, delete-orphan")
    mode = db.Column(db.String(20), default='html')

# Enable Write-Ahead Logging (WAL) mode for SQLite
# This significantly improves concurrency by allowing simultaneous readers and writers
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    conn_type = type(dbapi_connection).__module__
    if 'sqlite' not in conn_type:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    except:
        pass

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256)) # Increased length for scrypt hashes
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_muted = db.Column(db.Boolean, default=False)
    stardust = db.Column(db.Integer, default=0)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    @property
    def level_info(self):
        points = self.stardust
        if points >= 20000: return '星云', 'text-promethium'
        if points >= 15000: return '超新星', 'text-danger'
        if points >= 10000: return '白矮星', 'text-white-50'
        if points >= 7500: return '红巨星', 'text-danger'
        if points >= 5000: return '黄矮星', 'text-warning'
        if points >= 3000: return '红矮星', 'text-danger'
        if points >= 2000: return '巨行星', 'text-primary'
        if points >= 1000: return '行星', 'text-info'
        if points >= 500: return '卫星', 'text-secondary'
        if points >= 200: return '彗星', 'text-light'
        if points >= 100: return '小行星', 'text-muted'
        if points >= 50: return '流星', 'text-muted'
        return '星际尘埃', 'text-muted'

class StardustHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('stardust_history', lazy=True))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    score = db.Column(db.Integer, default=10)
    image = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), default='默认题集', index=True)
    mode = db.Column(db.String(20), default='html')
    type = db.Column(db.String(20), default='public', index=True)  # public/personal
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)  # 个人题目所属用户
    owner = db.relationship('User', backref=db.backref('personal_questions', lazy=True))
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'answer': self.answer,
            'score': self.score,
            'image': self.image,
            'category': self.category,
            'mode': self.mode,
            'type': self.type,
            'owner_id': self.owner_id
        }

class ExamResult(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('results', lazy=True))
    timestamp = db.Column(db.String(50), default=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    total_score = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=0)
    details_json = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), default='默认题集')
    @property
    def details(self):
        return json.loads(self.details_json) if self.details_json else []
    @details.setter
    def details(self, value):
        self.details_json = json.dumps(value, ensure_ascii=False)
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'level_info': self.user.level_info if self.user else ('', ''),
            'timestamp': self.timestamp,
            'total_score': self.total_score,
            'max_score': self.max_score,
            'details': self.details,
            'category': self.category or '默认题集'
        }

class UserCategoryStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    total_attempts = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)
    total_max_score = db.Column(db.Integer, default=0)
    user = db.relationship('User', backref=db.backref('category_stats', lazy=True))

class UserPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    user = db.relationship('User', backref=db.backref('permissions', lazy=True))

class SystemSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    mode = db.Column(db.String(20), default='html')  # 公告/指南编辑模式（html/markdown）

class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer, default=0)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    images_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    hotness = db.Column(db.Float, default=0.0, index=True)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    board = db.relationship('Board', backref=db.backref('topics', lazy=True, cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('topics', lazy=True))
    likes = db.relationship('TopicLike', backref='topic', lazy=True, cascade="all, delete-orphan")
    mode = db.Column(db.String(20), default='html')  # 新增字段，支持渲染模式
    @property
    def images(self):
        return json.loads(self.images_json or '[]')
    @images.setter
    def images(self, value):
        self.images_json = json.dumps(value)

    mode = db.Column(db.String(20), default='html')  # 新增字段，支持渲染模式

class TopicLike(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PostLike(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TopicView(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WorkshopWorkLike(db.Model):
    __tablename__ = 'workshop_work_like'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    work_id = db.Column(db.Integer, db.ForeignKey('workshop_work.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'work_id', name='uniq_user_work_like'),)


    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey('workshop_work.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- 参数初始化工具函数 ---
def init_workshop_system_settings():
    """
    自动补全工坊相关参数到 SystemSetting 表。
    可在 Flask shell 执行：from web.models import init_workshop_system_settings; init_workshop_system_settings()
    """
    from web.extensions import db
    from web.models import SystemSetting
    import json
    default_settings = [
        {
            'key': 'workshop_hotness_weights',
            'value': json.dumps({'w1': 0.2, 'w2': 1.2, 'g': 1.5}, ensure_ascii=False),
            'desc': '工坊热度权重参数'
        },
        {
            'key': 'workshop_hotness_milestones',
            'value': json.dumps([10, 30, 60, 120, 240, 480, 960, 1920], ensure_ascii=False),
            'desc': '工坊热度里程碑档位'
        },
        {
            'key': 'workshop_hotness_reward_formula',
            'value': json.dumps({'base': 10, 'factor': 1.5}, ensure_ascii=False),
            'desc': '工坊热度奖励算法参数'
        },
    ]
    for item in default_settings:
        setting = SystemSetting.query.get(item['key'])
        if not setting:
            setting = SystemSetting(key=item['key'], value=item['value'])
            db.session.add(setting)
        elif not setting.value:
            setting.value = item['value']
    db.session.commit()