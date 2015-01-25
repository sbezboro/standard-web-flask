from datetime import timedelta

from celery.schedules import crontab


DEBUG = False

WTF_CSRF_ENABLED = False

MEMCACHED_URLS = ['127.0.0.1:11211']

PERMANENT_SESSION_LIFETIME = timedelta(days=3650)

CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['application/json']

CELERYBEAT_SCHEDULE = {
    'minute-query': {
        'task': 'standardweb.jobs.query.minute_query',
        'schedule': crontab()
    },
    'db-backup': {
        'task': 'standardweb.jobs.backup.db_backup',
        'schedule': crontab(minute=0, hour=12)  # 4AM PST
    },
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
