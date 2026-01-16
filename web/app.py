# Flask工厂模式下静态资源版本号自动注入
import datetime
from __init__ import create_app, socketio

def get_static_version():
	# 可改为 git hash 或其他自动化方式
	return datetime.datetime.now().strftime('%Y%m%d%H%M')

def inject_static_version():
	return {'static_version': get_static_version()}

# Create the application instance
app = create_app()

# 注册 context_processor，确保 app 已实例化
app.context_processor(inject_static_version)

# 生产环境下不在此处启动 socketio.run，由 gunicorn + eventlet 启动
# 本地开发可用 flask run 或 python app.py