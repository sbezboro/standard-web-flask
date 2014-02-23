from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.cache import MemcachedCache

app = Flask(__name__)

db = SQLAlchemy(app)

cache = MemcachedCache(['127.0.0.1:11211'])

import middleware
import models
import template_filters
import views
