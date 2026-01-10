from web import create_app
from web.celery_utils import make_celery

app = create_app()
celery = make_celery(app)

import web.tasks
