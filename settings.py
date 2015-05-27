from datetime import timedelta

from celery.schedules import crontab
from kombu import Exchange, Queue


DEBUG = False

WTF_CSRF_ENABLED = False

MEMCACHED_URLS = ['127.0.0.1:11211']

PERMANENT_SESSION_LIFETIME = timedelta(days=3650)

CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_DEFAULT_QUEUE = 'default'
CELERY_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('minute_query', Exchange('minute_query'), routing_key='minute_query'),
    Queue('check_uuids', Exchange('check_uuids'), routing_key='check_uuids'),
)

CELERYBEAT_SCHEDULE = {
    'minute_query': {
        'task': 'standardweb.jobs.query.minute_query',
        'schedule': crontab()
    },
    'db_backup': {
        'task': 'standardweb.jobs.backup.db_backup',
        'schedule': crontab(minute=0, hour=12)  # 4AM PST
    },
    'check_uuids': {
        'task': 'standardweb.jobs.usernames.check_uuids',
        'schedule': timedelta(minutes=4)  # Every 4 minutes
    }
}

CELERY_ROUTES = {
    'standardweb.jobs.query.minute_query': {
        'queue': 'minute_query'
    },
    'standardweb.jobs.usernames.schedule_checks': {
        'queue': 'check_uuids'
    }
}

ASSETS_DEBUG = False
ASSETS_AUTO_BUILD = False
UGLIFYJS_EXTRA_ARGS = ['-c', '-m']

FLASK_ASSETS_USE_CDN = True
CDN_DOMAIN = 'd2rpyddsvhacm5.cloudfront.net'

try:
    from local_settings import *
except ImportError:
    pass
