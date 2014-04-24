from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.cache import MemcachedCache

app = Flask(__name__)

app.jinja_env.add_extension('jinja2.ext.loopcontrols')

db = SQLAlchemy(app)

cache = MemcachedCache(['127.0.0.1:11211'])

import api
import middleware
import models
import template_filters
import views
