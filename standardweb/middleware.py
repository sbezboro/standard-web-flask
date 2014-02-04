from flask import abort
from flask import g
from flask import request
from flask import session

from jinja2.nodes import Markup

from standardweb import app
from standardweb.lib import csrf
from standardweb.models import User


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
                csrf.regenerate_token()
                abort(403)


@app.context_processor
def inject_user():
    return dict(user=getattr(g, 'user', None))
