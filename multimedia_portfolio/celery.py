import os
from celery import Celery

# Default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multimedia_portfolio.settings')

app = Celery('multimedia_portfolio')

# Read config from Django settings, using CELERY_ namespace for Celery-related keys
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    return f"Request: {self.request!r}"
