import os
import sys

# Ensure web path is in sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web'))

from web.app import app
from web.celery_utils import make_celery

# Initialize Celery app
celery_app = make_celery(app)

# Explicitly import tasks to register them
import web.tasks
