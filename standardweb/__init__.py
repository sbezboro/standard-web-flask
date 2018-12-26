import socket
import traceback

from celery import Celery
from celery.schedules import crontab
from flask import Flask, g, got_request_exception, Request
from flask_cdn import CDN
from flask_sqlalchemy import SQLAlchemy
from kombu import Queue, Exchange
import rollbar
from rollbar.contrib.flask import report_exception
import statsd
from werkzeug.contrib.cache import MemcachedCache
from werkzeug.contrib.fixers import ProxyFix


app = Flask(__name__)

app.config.from_object('settings')

app.jinja_env.add_extension('jinja2.ext.loopcontrols')

app.wsgi_app = ProxyFix(app.wsgi_app)

db = SQLAlchemy(app)

cdn = CDN(app)

cache = MemcachedCache(app.config['MEMCACHED_URLS'])

try:
    stats = statsd.StatsClient(host=app.config['STATSD_HOST'], port=app.config['STATSD_PORT'])
except socket.gaierror:
    stats = statsd.StatsClient()


def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])

    celery.conf.update(app.config)
    celery.conf.update({
        'CELERY_DEFAULT_QUEUE': 'default',
        'CELERY_QUEUES': (
            Queue('default', Exchange('default'), routing_key='default'),
            Queue('minute_query', Exchange('minute_query'), routing_key='minute_query'),
            Queue('check_uuids', Exchange('check_uuids'), routing_key='check_uuids'),
        ),
        'CELERY_ROUTES': {
            'standardweb.jobs.query.minute_query': {
                'queue': 'minute_query'
            },
            'standardweb.jobs.usernames.check_uuids': {
                'queue': 'check_uuids'
            }
        },
        'CELERYBEAT_SCHEDULE': {
            'minute_query': {
                'task': 'standardweb.jobs.query.minute_query',
                'schedule': crontab()
            },
            'db_backup': {
                'task': 'standardweb.jobs.backup.db_backup',
                'schedule': crontab(minute=0, hour=10)  # 3AM PST
            },
            #'check_uuids': {
            #    'task': 'standardweb.jobs.usernames.check_uuids',
            #    'schedule': timedelta(minutes=4)  # Every 4 minutes
            #}
        }
    })

    TaskBase = celery.Task

    # don't wrap tasks with app contexts in development
    # since the tasks are run synchronously
    if app.config.get('CELERY_ALWAYS_EAGER'):
        class ContextTask(TaskBase):
            abstract = True

            def on_failure(self, exc, task_id, args, kwargs, einfo):
                traceback.print_exc()
                rollbar.report_exc_info()
    else:
        class ContextTask(TaskBase):
            abstract = True

            def __call__(self, *args, **kwargs):
                with app.app_context():
                    g.user = None
                    return TaskBase.__call__(self, *args, **kwargs)

            def on_failure(self, exc, task_id, args, kwargs, einfo):
                rollbar.report_exc_info()

    celery.Task = ContextTask

    return celery


celery = make_celery(app)


def set_up_rollbar():
    class CustomRequest(Request):
        @property
        def rollbar_person(self):
            if g.user:
                user = g.user

                return {
                    'id': user.id,
                    'username': user.get_username(),
                    'email': user.email
                }

    rollbar.init(
        app.config['ROLLBAR_ACCESS_TOKEN'],
        app.config['ROLLBAR_ENVIRONMENT'],
        root=app.config['ROLLBAR_ROOT'],
        handler='blocking',
        allow_logging_basic_config=False,
        timeout=5
    )

    got_request_exception.connect(report_exception, app)

    app.request_class = CustomRequest


if app.config.has_key('ROLLBAR_ACCESS_TOKEN'):
    set_up_rollbar()

import assets

import jobs.query
import jobs.backup
import jobs.usernames

import middleware
import models

import tasks.access_log
import tasks.email
import tasks.messages
import tasks.notifications
import tasks.realtime
import tasks.server_api

import template_filters

import views.admin
import views.api
import views.auth
import views.forums
import views.groups
import views.ip
import views.main
import views.messages
import views.notifications
import views.player
import views.settings
import views.static_files
