import os
from celery import Celery

# Stel de standaard Django settings module in
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoproject.settings')

app = Celery('djangoproject')

# Laad config van settings.py, alles startend met CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Ontdek taken in alle installed apps
app.autodiscover_tasks()
