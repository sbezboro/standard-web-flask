from flask import abort
from flask import g
from flask import request
from flask import session
from flask import url_for

from standardweb import app
from standardweb.lib import csrf
from standardweb.lib import helpers as h
from standardweb.models import Message, User
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


@app.before_request
def first_login():
    first_login = False

    if request.endpoint and 'static' not in request.endpoint \
            and request.endpoint != 'face' and session.get('user_id'):
        if 'first_login' in session:
            first_login = session.pop('first_login')

    g.first_login = first_login


@app.context_processor
def inject_user():
    return dict(user=g.user)


@app.context_processor
def inject_h():
    return dict(h=h)


@app.context_processor
def inject_debug():
    return dict(is_debug=app.config['DEBUG'])


@app.context_processor
def inject_new_messages():
    new_messages = 0

    if g.user:
        new_messages = len(
            Message.query.with_entities(Message.id).filter_by(
                to_user=g.user,
                seen_at=None
            ).all()
        )

    return dict(new_messages=new_messages)


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
        uuid = g.user.player.uuid if g.user.player else ''
        admin = g.user.admin

        content = '-'.join([str(user_id), username, uuid, str(int(admin))])

        token = hashlib.sha256(content + app.config['RTS_SECRET']).hexdigest()

        data = {
            'user_id': user_id,
            'username': username,
            'uuid': uuid,
            'is_superuser': int(admin),
            'token': token
        }

    return {
        'rts_address': app.config['RTS_ADDRESS'],
        'rts_auth_data': data
    }
