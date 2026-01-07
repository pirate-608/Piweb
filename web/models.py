from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()

# Enable Write-Ahead Logging (WAL) mode for SQLite
# This significantly improves concurrency by allowing simultaneous readers and writers
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Only run for SQLite connections
    # Check if the connection has 'execute' method directly (sqlite3) or via cursor
    # But simpler is to check the module/type name
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
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    score = db.Column(db.Integer, default=10)
    image = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), default='默认题集', index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'answer': self.answer,
            'score': self.score,
            'image': self.image,
            'category': self.category
        }

class ExamResult(db.Model):
    id = db.Column(db.String(36), primary_key=True) # UUID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Link to User
    user = db.relationship('User', backref=db.backref('results', lazy=True))
    
    timestamp = db.Column(db.String(50), default=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    total_score = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=0)
    details_json = db.Column(db.Text, nullable=True) # Store details as JSON string

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
            'timestamp': self.timestamp,
            'total_score': self.total_score,
            'max_score': self.max_score,
            'details': self.details
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

# Forum Models
class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer, default=0) # For sorting
    
    # Relationships
    # topics = db.relationship('Topic', backref='board', lazy=True, cascade="all, delete-orphan")

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
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False) # Soft delete
    
    board = db.relationship('Board', backref=db.backref('topics', lazy=True, cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('topics', lazy=True))
    likes = db.relationship('TopicLike', backref='topic', lazy=True, cascade="all, delete-orphan")

    @property
    def images(self):
        return json.loads(self.images_json or '[]')
    
    @images.setter
    def images(self, value):
        self.images_json = json.dumps(value)

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

class TopicLike(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

