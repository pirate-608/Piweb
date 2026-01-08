import os
import sys

# Import create_app from web package
# We appended 'web' to sys.path, but cleaner is to append the root and import web.create_app
# Current logic appends 'web'. So 'from __init__ import create_app' works if we are treating 'web' directory as root for imports,
# but usually we want 'from web import create_app'.

# Let's clean up the path injection to be more standard.
# If we run from project root, 'web' is a package.
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Also append 'web' directory to sys.path to support legacy imports (e.g. 'import config', 'from utils...')
web_dir = os.path.join(root_dir, 'web')
if web_dir not in sys.path:
    sys.path.append(web_dir)

from web import create_app
from web.celery_utils import make_celery

app = create_app()
celery_app = make_celery(app)

# Explicitly import tasks to register them
import web.tasks
