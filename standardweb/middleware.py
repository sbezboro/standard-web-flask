from flask import abort
from flask import g
from flask import request
from flask import session
from flask import url_for

from standardweb import app
from standardweb.lib import csrf
from standardweb.lib import helpers as h
from standardweb.models import User
from sqlalchemy.orm import joinedload

import hashlib
import os


@app.before_request
def user_session():
    if request.endpoint and 'static' not in request.endpoint \
            and request.endpoint != 'face' and session.get('user_id'):
        
        g.user = User.query.options(
            joinedload(User.player)
        ).options(
            joinedload(User.posttracking)
        ).get(session['user_id'])
    else:
        g.user = None


@app.before_request
def csrf_protect():
    if request.method == "POST":
        func = app.view_functions.get(request.endpoint)

        if func and func not in csrf.exempt_funcs and 'debugtoolbar' not in request.endpoint:
            token = session.get('csrf_token')

            if not token or token != request.form.get('csrf_token'):
                csrf.regenerate_token()
                abort(403)


@app.context_processor
def inject_user():
    return dict(user=getattr(g, 'user', None))


@app.context_processor
def inject_h():
    return dict(h=h)


def _dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)

        if filename:
            file_path = os.path.join(app.root_path, endpoint, filename)
            try:
                values['t'] = int(os.stat(file_path).st_mtime)
            except:
                pass

    return url_for(endpoint, **values)


@app.context_processor
def override_url_for():
    return dict(url_for=_dated_url_for)


@app.context_processor
def rts_auth_data():
    data = {}

    if g.user:
        user_id = g.user.id
        username = g.user.player.username if g.user.player else g.user.username
        admin = g.user.admin

        content = '-'.join([str(user_id), username, str(int(admin))])

        token = hashlib.sha256(content + app.config['RTS_SECRET']).hexdigest()

        data = {
            'user_id': user_id,
            'username': username,
            'is_superuser': int(admin),
            'token': token
        }

    return {
        'rts_address': app.config['RTS_ADDRESS'],
        'rts_auth_data': data
    }
