from flask import abort
from flask import request
from flask import request_started
from flask import session

from jinja2.nodes import Markup

from standardweb import app
from standardweb.models import User

import os


def user_session(sender, **extra):
    if session.get('user_id'):
        setattr(request, 'user', User.query.get(session['user_id']))

request_started.connect(user_session, app)


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('csrf_token')

        if not token or token != request.form.get('csrf_token'):
            session.pop('csrf_token', None)
            abort(403)


def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = os.urandom(40).encode('hex')

    return Markup('<input type="hidden" name="csrf_token" value="%s" />' % session['csrf_token'])

app.jinja_env.globals['csrf_token'] = generate_csrf_token
