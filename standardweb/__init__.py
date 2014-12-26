import traceback

from celery import Celery
from flask import Flask
from flask import g
from flask import got_request_exception
from flask import Request
from flask.ext.cdn import CDN
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.cache import MemcachedCache

import rollbar
from rollbar.contrib.flask import report_exception


app = Flask(__name__)

app.config.from_object('settings')

app.jinja_env.add_extension('jinja2.ext.loopcontrols')

db = SQLAlchemy(app)

cdn = CDN(app)

cache = MemcachedCache(app.config['MEMCACHED_URLS'])


def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])

    celery.conf.update(app.config)

    TaskBase = celery.Task

    # don't wrap tasks with app contexts in development
    # since the tasks are run inline
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
        allow_logging_basic_config=False
    )

    got_request_exception.connect(report_exception, app)

    app.request_class = CustomRequest


if app.config.has_key('ROLLBAR_ACCESS_TOKEN'):
    set_up_rollbar()

import assets
import middleware
import models
import tasks
import template_filters

import views.api
import views.auth
import views.base
import views.forums
import views.groups
import views.messages
import views.settings
