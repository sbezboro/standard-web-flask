from celery.schedules import crontab

DEBUG = False

WTF_CSRF_ENABLED = False

MEMCACHED_URLS = ['127.0.0.1:11211']

CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['application/json']

CELERYBEAT_SCHEDULE = {
    'minute-query': {
        'task': 'standardweb.tasks.minute_query',
        'schedule': crontab()
    },
}

try:
    from local_settings import *
except ImportError:
    pass
