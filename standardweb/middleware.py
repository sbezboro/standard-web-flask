from flask import abort
from flask import g
from flask import request
from flask import session

from jinja2.nodes import Markup

from standardweb import app
from standardweb.lib import csrf
from standardweb.models import User

import os


@app.before_request
def user_session():
    if request.endpoint and 'static' not in request.endpoint and session.get('user_id'):
        g.user = User.query.get(session['user_id'])


@app.before_request
def csrf_protect():
    if request.method == "POST":
        func = app.view_functions.get(request.endpoint)

        if func and func not in csrf.exempt_funcs:
            token = session.get('csrf_token')

            if not token or token != request.form.get('csrf_token'):
                session.pop('csrf_token', None)
                abort(403)


def _generate_csrf_token_field():
    if 'csrf_token' not in session:
        session['csrf_token'] = os.urandom(40).encode('hex')

    return Markup('<input type="hidden" name="csrf_token" value="%s" />' % session['csrf_token'])

app.jinja_env.globals['csrf_token'] = _generate_csrf_token_field


@app.context_processor
def inject_user():
    return dict(user=g.user)