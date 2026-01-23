
# ---- gevent patch_all 必须最早 ----
import gevent.monkey
gevent.monkey.patch_all(ssl=True, aggressive=True)

from web import create_app
from web.celery_utils import make_celery

app = create_app()
celery = make_celery(app)

import web.tasks
