from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)

db = SQLAlchemy(app)

import middleware
import models
import template_filters
import views
