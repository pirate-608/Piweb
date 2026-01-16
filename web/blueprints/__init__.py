# 导入各个蓝图对象，便于主app统一注册
from .main import main_bp
from .auth import auth_bp
from .forum import forum_bp
from .exam import exam_bp

# 可选：统一导出，方便IDE补全
__all__ = [
	'main_bp',
	'auth_bp',
	'forum_bp',
	'exam_bp',
]
# 使 blueprints 成为 Python 包
