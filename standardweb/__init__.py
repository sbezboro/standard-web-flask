from flask import Flask
from flask import g
from flask import got_request_exception
from flask import Request
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.cache import MemcachedCache
import rollbar
from rollbar.contrib.flask import report_exception


app = Flask(__name__)

app.config.from_object('settings')

app.jinja_env.add_extension('jinja2.ext.loopcontrols')

db = SQLAlchemy(app)

cache = MemcachedCache(['127.0.0.1:11211'])

import middleware
import models
import template_filters

import views.api
import views.auth
import views.forums
import views.main


def set_up_rollbar():
    class CustomRequest(Request):
        @property
        def rollbar_person(self):
            if g.user:
                user = g.user

                return {
                    'id': user.id,
                    'username': user.player.username if user.player else user.username,
                    'email': user.email
                }

    rollbar.init(app.config['ROLLBAR_ACCESS_TOKEN'],
                 app.config['ROLLBAR_ENVIRONMENT'],
                 root=app.config['ROLLBAR_ROOT'],
                 handler='blocking',
                 allow_logging_basic_config=False)

    got_request_exception.connect(report_exception, app)

    app.request_class = CustomRequest

if app.config.has_key('ROLLBAR_ACCESS_TOKEN'):
    set_up_rollbar()